from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models.models import db, User, Ticket, TicketHistory, TicketComment, TicketAttachment
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory
from email_to_ticket import send_confirmation_email, send_update_email
from flask import abort
from datetime import datetime, timedelta
from sqlalchemy import func

# Detectar ambiente
env = os.environ.get('FLASK_ENV', 'development')

if env == 'production':
    from config_prod import ProductionConfig as Config
else:
    from config_dev import DevelopmentConfig as Config

app = Flask(__name__)
app.config.from_object(Config)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    open_count = Ticket.query.filter_by(status='Aberto').count()
    in_progress_count = Ticket.query.filter_by(status='Em Andamento').count()
    closed_count = Ticket.query.filter_by(status='Encerrado').count()
    # Média de resolução
    avg_resolution = db.session.query(
        func.avg(func.extract('epoch', Ticket.updated_at - Ticket.created_at))
    ).filter(Ticket.status == 'Encerrado').scalar()

    if avg_resolution:
        avg_seconds = int(avg_resolution)
        avg_days = avg_seconds // (24 * 3600)
        avg_hours = (avg_seconds % (24 * 3600)) // 3600
        avg_time_text = f"{avg_days}d {avg_hours}h"
    else:
        avg_time_text = "N/A"

    return render_template(
        'index.html',
        user=current_user,
        open_count=open_count,
        in_progress_count=in_progress_count,
        closed_count=closed_count,
        avg_resolution=avg_time_text
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/tickets')
@login_required
def tickets():
    all_tickets = Ticket.query.order_by(Ticket.id.asc()).all()
    return render_template('tickets.html', tickets=all_tickets, datetime=datetime, timedelta=timedelta)

@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def view_ticket(ticket_id):
    users = User.query.filter(User.is_active == True, User.profile.in_(['Administrador', 'Suporte'])).all()
    ticket = Ticket.query.get_or_404(ticket_id)
    history = TicketHistory.query.filter_by(ticket_id=ticket.id).order_by(TicketHistory.changed_at.desc()).all()
    comments = TicketComment.query.filter_by(ticket_id=ticket.id).order_by(TicketComment.commented_at.desc()).all()
    attachments = TicketAttachment.query.filter_by(ticket_id=ticket.id).all()

    if request.method == 'POST':
        # ✅ Upload de arquivo (anexo separado)
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            if file:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                db.session.add(TicketAttachment(
                    ticket_id=ticket.id,
                    filename=filename,
                    filepath=filepath
                ))
                db.session.commit()
                flash('Arquivo anexado com sucesso!')
                return redirect(url_for('view_ticket', ticket_id=ticket.id))

        # ✅ Atualizar status, prioridade, responsável e comentário
        old_status = ticket.status
        old_priority = ticket.priority
        old_assigned = ticket.assigned_to or 'Não atribuído'

        new_status = request.form.get('status')
        new_priority = request.form.get('priority')
        new_assigned = request.form.get('assigned_to')
        comment_text = request.form.get('comment')

        changes = []
        if old_status != new_status:
            changes.append(f"Status: '{old_status}' ➔ '{new_status}'")
            ticket.status = new_status
        if old_priority != new_priority:
            changes.append(f"Prioridade: '{old_priority}' ➔ '{new_priority}'")
            ticket.priority = new_priority
        if (ticket.assigned_to or '') != (new_assigned or ''):
            changes.append(f"Responsável: '{old_assigned}' ➔ '{new_assigned or 'Não atribuído'}'")
            ticket.assigned_to = new_assigned if new_assigned else None

        # 💬 Comentário adicionado?
        comment_added = False
        if comment_text and comment_text.strip():
            db.session.add(TicketComment(
                ticket_id=ticket.id,
                commenter=current_user.username,
                comment=comment_text.strip()
            ))
            comment_added = True

        # 🔄 Histórico (se houve mudanças)
        if changes:
            db.session.add(TicketHistory(
                ticket_id=ticket.id,
                changed_by=current_user.username,
                change_description="; ".join(changes)
            ))

        db.session.commit()

        # 🔔 Enviar e-mail (exceto se status = Cancelado)
        if (changes or comment_added) and new_status != 'Cancelado':
            body_msg = ""
            if changes:
                body_msg += "🔄 Alterações:\n" + "\n".join(changes)
            if comment_added:
                body_msg += f"\n\n💬 Comentário:\n\"{comment_text.strip()}\""
            send_update_email(
                ticket,
                ticket.requester_email,
                ticket.requester_name,
                "Ticket Atualizado",
                body_msg
            )
            flash('Alterações salvas e e-mail enviado!')
        else:
            flash('Alterações salvas!')

        return redirect(url_for('view_ticket', ticket_id=ticket.id))

    return render_template(
        'view_ticket.html',
        ticket=ticket,
        history=history,
        comments=comments,
        attachments=attachments,
        users=users
    )

@app.route('/uploads/<path:filename>')
@login_required
def download_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/new_ticket', methods=['GET', 'POST'])
@login_required
def new_ticket():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority')
        requester_name = request.form.get('requester_name')
        requester_email = request.form.get('requester_email')

        new_ticket = Ticket(
            title=title,
            description=description,
            status='Aberto',
            priority=priority,
            requester_email=requester_email,
            requester_name=requester_name
        )
        db.session.add(new_ticket)
        db.session.commit()

        file = request.files.get('file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            attachment = TicketAttachment(
                ticket_id=new_ticket.id,
                filename=filename,
                filepath=filepath
            )
            db.session.add(attachment)
            db.session.commit()
            print(f"Anexo {filename} salvo para o ticket #{new_ticket.id}")

        try:
            send_confirmation_email(new_ticket, requester_email, requester_name)
            print(f"E-mail de confirmação enviado para {requester_email}")
        except Exception:
            print("❌ Falha ao enviar e-mail de confirmação")

        flash('Ticket criado com sucesso!')
        return redirect(url_for('tickets'))
    return render_template('new_ticket.html')

@app.route('/users')
@login_required
def users():
    if current_user.profile != 'Administrador':
        abort(403)
    all_users = User.query.order_by(User.id.asc()).all()
    return render_template('users.html', users=all_users)

@app.route('/new_user', methods=['GET', 'POST'])
@login_required
def new_user():
    if current_user.profile != 'Administrador':
        abort(403)
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        profile = request.form.get('profile')

        new_user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=password,
            profile=profile,
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Usuário criado com sucesso!')
        return redirect(url_for('users'))
    return render_template('new_user.html')

@app.route('/toggle_user_status/<int:user_id>')
@login_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'Usuário {user.username} {"ativado" if user.is_active else "desativado"}!')
    return redirect(url_for('users'))

@app.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuário {user.username} excluído com sucesso!')
    return redirect(url_for('users'))

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.profile != 'Administrador':
        abort(403)
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.profile = request.form.get('profile')
        new_password = request.form.get('password')
        if new_password:
            user.password = new_password
        db.session.commit()
        flash('Usuário atualizado com sucesso!')
        return redirect(url_for('users'))
    return render_template('edit_user.html', user=user)

@app.route('/my_tickets')
@login_required
def my_tickets():
    my_tickets = Ticket.query.filter(
        Ticket.assigned_to == current_user.username,
        Ticket.status.notin_(['Encerrado', 'Cancelado'])
    ).order_by(Ticket.id.asc()).all()
    return render_template('tickets.html', tickets=my_tickets, datetime=datetime, timedelta=timedelta)

if __name__ == '__main__':
    # 🚀 Rodar em portas diferentes por ambiente
    env = os.environ.get('FLASK_ENV', 'development')
    port = 5000 if env == 'production' else 5001
    app.run(host='0.0.0.0', port=port, debug=True)
