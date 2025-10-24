from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models.models import db, User, Ticket, TicketHistory, TicketComment, TicketAttachment, Asset, CostCenter, DeviceUser, AssetType, EstoqueMovimentacao
from email_to_ticket import send_confirmation_email, send_update_email
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import func, text, asc, desc
from config_dev import Config
from routes.routes_ativos import bp_ativos
import os

# ✅ Criação da aplicação Flask
app = Flask(__name__)
app.config.from_object(Config)

# 📂 Caminho global de uploads (melhor prática Flask)
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads', 'attachments')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ✅ Inicializa o banco de dados
db.init_app(app)

# ✅ Importa e registra os Blueprints após o app ser criado
from routes.routes_avatar import avatar_bp   
from routes.routes_estoque import estoque_bp
from routes.routes_usuarios_dispositivo import usuarios_dispositivo_bp
from routes.routes_ativos import bp_ativos

app.register_blueprint(avatar_bp, url_prefix='/avatar')
app.register_blueprint(estoque_bp)
app.register_blueprint(usuarios_dispositivo_bp)
app.register_blueprint(bp_ativos)
#Final dos registros do blueprint*******************************

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    # ===== Chamados =====
    open_count = Ticket.query.filter_by(status='Aberto').count()
    in_progress_count = Ticket.query.filter_by(status='Em Andamento').count()
    closed_count = Ticket.query.filter_by(status='Encerrado').count()

    # Tempo médio de resolução (minutos → d h m)
    avg_resolution = db.session.query(
        func.avg(text("TIMESTAMPDIFF(MINUTE, tickets.created_at, tickets.updated_at)"))
    ).filter(Ticket.status == 'Encerrado').scalar()

    if avg_resolution:
        avg_seconds = int(avg_resolution * 60)
        avg_days = avg_seconds // (24 * 3600)
        avg_hours = (avg_seconds % (24 * 3600)) // 3600
        avg_minutes = (avg_seconds % 3600) // 60
        avg_time_text = f"{avg_days}d {avg_hours}h {avg_minutes}m"
    else:
        avg_time_text = "N/A"

    # ===== Ativos (todos os tipos existentes no banco) =====
    ativos_raw = (
        db.session.query(AssetType.name, func.count(Asset.id))
        .join(Asset, Asset.type_id == AssetType.id, isouter=True)
        .group_by(AssetType.name)
        .order_by(func.count(Asset.id).desc())
        .all()
    )

    if ativos_raw:
        ativos_labels = [row[0] if row[0] else "Sem tipo" for row in ativos_raw]
        ativos_counts = [row[1] for row in ativos_raw]
    else:
        ativos_labels = ["Sem dados"]
        ativos_counts = [0]

    # ✅ Cria pares (para a tabela do dashboard)
    ativos_zip = list(zip(ativos_labels, ativos_counts))

    # ===== Movimentações recentes do estoque =====
    movimentacoes = (
        EstoqueMovimentacao.query
        .order_by(EstoqueMovimentacao.timestamp.desc())
        .limit(5)
        .all()
    )

    # ===== Renderização =====
    return render_template(
        'index.html',
        user=current_user,
        open_count=open_count,
        in_progress_count=in_progress_count,
        closed_count=closed_count,
        avg_resolution=avg_time_text,
        movimentacoes=movimentacoes,
        ativos_labels=ativos_labels,
        ativos_counts=ativos_counts,
        ativos_zip=ativos_zip  # ✅ Enviando pro HTML
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


@app.route('/new_ticket', methods=['GET', 'POST'])
@login_required
def new_ticket():
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            description = request.form.get('description')
            priority = request.form.get('priority')
            requester_name = request.form.get('requester_name')
            requester_email = request.form.get('requester_email')

            # === Avatar automático com base no e-mail ===
            email_prefix = requester_email.split('@')[0].lower() if requester_email else None
            avatar_filename = None

            # Caminho base dos avatares
            avatar_dir = os.path.join(app.static_folder, 'uploads', 'avatars')

            # Verifica se existe um avatar com o prefixo do e-mail
            if email_prefix:
                for ext in ['.jpg', '.jpeg', '.png']:
                    possible_path = os.path.join(avatar_dir, f"{email_prefix}{ext}")
                    if os.path.exists(possible_path):
                        avatar_filename = f"{email_prefix}{ext}"
                        break

            # Se não tiver imagem específica, usa o padrão
            if not avatar_filename:
                avatar_filename = 'default-avatar.png'

            # === Criação do novo ticket ===
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

            # === Upload de arquivo, se existir ===
            file = request.files.get('file')
            if file and file.filename.strip():
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                attachment = TicketAttachment(
                    ticket_id=new_ticket.id,
                    filename=filename,
                    filepath=filepath
                )
                db.session.add(attachment)
                db.session.commit()

            # === Envia e-mail de confirmação ===
            try:
                send_confirmation_email(new_ticket, requester_email, requester_name)
                flash('✅ Ticket criado com sucesso! E-mail de confirmação enviado.', 'success')
            except Exception as e:
                print(f"⚠️ Falha ao enviar e-mail: {e}")
                flash('✅ Ticket criado com sucesso, mas o e-mail não pôde ser enviado.', 'warning')

            return redirect(url_for('my_tickets'))

        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar ticket: {e}")
            flash('❌ Ocorreu um erro ao criar o ticket. Verifique os dados e tente novamente.', 'danger')
            return redirect(url_for('new_ticket'))

    return render_template('new_ticket.html')


@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def view_ticket(ticket_id):
    users = User.query.filter(User.is_active == True, User.profile.in_(['Administrador', 'Suporte'])).all()
    ticket = Ticket.query.get_or_404(ticket_id)
    history = TicketHistory.query.filter_by(ticket_id=ticket.id).order_by(TicketHistory.changed_at.desc()).all()
    comments = TicketComment.query.filter_by(ticket_id=ticket.id).order_by(TicketComment.commented_at.desc()).all()
    attachments = TicketAttachment.query.filter_by(ticket_id=ticket.id).all()

    if request.method == 'POST':
        # Upload de arquivo
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
                flash('📎 Arquivo anexado com sucesso!', 'success')
                return redirect(url_for('view_ticket', ticket_id=ticket.id))

        # Atualização de dados
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

        comment_added = False
        if comment_text and comment_text.strip():
            db.session.add(TicketComment(
                ticket_id=ticket.id,
                commenter=current_user.username,
                comment=comment_text.strip()
            ))
            comment_added = True

        if changes:
            db.session.add(TicketHistory(
                ticket_id=ticket.id,
                changed_by=current_user.username,
                change_description="; ".join(changes)
            ))

        db.session.commit()

        # 🔹 Envio de e-mail e mensagens
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

            # ✅ Mensagens personalizadas conforme status
            if new_status in ['Encerrado', 'Concluído', 'Fechado']:
                flash('✅ Ticket concluído com sucesso!', 'success')
            else:
                flash('📝 Alterações salvas e e-mail enviado!', 'success')
        else:
            flash('📝 Alterações salvas!', 'success')

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
    # Página atual (?page=2)
    page = request.args.get('page', 1, type=int)

    # Filtros vindos da URL
    status_filter = request.args.get('status_filter', '').strip()
    responsavel_filter = request.args.get('responsavel_filter', '').strip()

    # Base da query
    query = Ticket.query

    # 🔹 Filtro de status
    if status_filter == 'Aberto':
        query = query.filter(Ticket.status == 'Aberto')
    elif status_filter == 'Em Andamento':
        query = query.filter(Ticket.status == 'Em Andamento')
    elif status_filter == 'Fechados':
        query = query.filter(Ticket.status.in_(['Encerrado', 'Cancelado']))

    # 🔹 Filtro de responsável (busca parcial)
    if responsavel_filter:
        query = query.filter(Ticket.assigned_to.ilike(f"%{responsavel_filter}%"))

    # Ordenação
    query = query.order_by(Ticket.id.desc())

    # Paginação
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    tickets = pagination.items

    # 🕒 Cálculo do SLA com minutos e congelamento ao encerrar
    for t in tickets:
        if not t.created_at:
            t.sla = {"texto": "—", "cor": "text-muted"}
            continue

        fim = t.updated_at if t.status in ['Encerrado', 'Cancelado'] and t.updated_at else datetime.now()
        tempo_decorrido = (fim - t.created_at).total_seconds()

        horas_totais = tempo_decorrido / 3600
        dias = int(horas_totais // 24)
        horas = int(horas_totais % 24)
        minutos = int((tempo_decorrido % 3600) / 60)

        if dias > 0:
            texto_sla = f"{dias}d {horas}h {minutos}m"
        elif horas > 0:
            texto_sla = f"{horas}h {minutos}m"
        else:
            texto_sla = f"{minutos}m"

        if horas_totais <= 4:
            cor = "text-success fw-bold"   # Verde
        elif horas_totais <= 8:
            cor = "text-warning fw-bold"   # Amarelo
        else:
            cor = "text-danger fw-bold"    # Vermelho

        t.sla = {"texto": texto_sla, "cor": cor}

    # Renderiza com paginação e filtros mantidos
    return render_template(
        'tickets.html',
        tickets=tickets,
        datetime=datetime,
        timedelta=timedelta,
        total_pages=pagination.pages,
        current_page=pagination.page,
        has_prev=pagination.has_prev,
        has_next=pagination.has_next,
        prev_page=pagination.prev_num,
        next_page=pagination.next_num,
        request=request  # 👈 necessário pro template lembrar os filtros
    )



#Inicio do codigo (rota) para a tela de ativos
@app.route('/ativos')
@login_required
def ativos():
    ativos = (
        db.session.query(
            Asset.id,
            Asset.brand,
            Asset.model,
            Asset.status,
            Asset.acquisition_date,
            DeviceUser.first_name,
            DeviceUser.last_name,
            CostCenter.name.label('cc_nome'),
            AssetType.name.label('asset_type')
        )
        .join(DeviceUser, Asset.device_user_id == DeviceUser.id, isouter=True)
        .join(CostCenter, Asset.cost_center_id == CostCenter.id, isouter=True)
        .join(AssetType, Asset.type_id == AssetType.id, isouter=True)
        .order_by(Asset.id.desc())
        .all()
    )

    tipos = AssetType.query.all()
    usuarios = DeviceUser.query.all()
    centros = CostCenter.query.all()

    # Dados dos gráficos
    ativos_por_tipo = dict(db.session.query(AssetType.name, func.count(Asset.id)).join(Asset).group_by(AssetType.name).all())
    ativos_por_cc = dict(db.session.query(CostCenter.name, func.count(Asset.id)).join(Asset).group_by(CostCenter.name).all())
    ativos_por_departamento = dict(db.session.query(DeviceUser.department, func.count(Asset.id)).join(Asset).group_by(DeviceUser.department).all())

    return render_template(
        'ativos.html',
        ativos=ativos,
        tipos=tipos,
        usuarios=usuarios,
        centros=centros,
        ativos_por_tipo=ativos_por_tipo,
        ativos_por_cc=ativos_por_cc,
        ativos_por_departamento=ativos_por_departamento
    )



@app.route('/ativos/check_serial')
@login_required
def check_serial():
    serial_number = request.args.get('serial_number', '').strip()
    exists = bool(Asset.query.filter_by(serial_number=serial_number).first())
    return jsonify({'exists': exists})



# ======================================
# ROTA: Novo Ativo
# ======================================
@app.route('/ativos/novo', methods=['POST'])
@login_required
def novo_ativo():
    try:
        serial_number = request.form.get('serial_number')

        # 🚫 Verifica duplicidade
        if Asset.query.filter_by(serial_number=serial_number).first():
            flash(f"⚠️ Já existe um ativo com o número de série '{serial_number}'.", 'warning')
            return redirect(url_for('ativos'))

        type_id = request.form.get('type_id')
        tipo = AssetType.query.get(type_id)

        if not tipo:
            flash('❌ Tipo de dispositivo inválido.', 'danger')
            return redirect(url_for('ativos'))

        ativo = Asset(
            asset_type=tipo.name,
            type_id=type_id,
            brand=request.form.get('brand'),
            model=request.form.get('model'),
            serial_number=serial_number,
            hostname=request.form.get('hostname'),
            invoice_number=request.form.get('invoice_number'),
            patrimony_code=request.form.get('patrimony_code'),
            status=request.form.get('status'),
            ownership=request.form.get('ownership'),
            location=request.form.get('location'),
            cost_center_id=request.form.get('cost_center_id') or None,
            device_user_id=request.form.get('device_user_id') or None,
            acquisition_date=request.form.get('acquisition_date') or None,
            return_date=request.form.get('return_date') or None,
            notes=request.form.get('notes')
        )

        db.session.add(ativo)
        db.session.commit()

        flash("✅ Ativo cadastrado com sucesso!", "success")
        return redirect(url_for('ativos'))

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao cadastrar ativo: {e}", "danger")
        return redirect(url_for('ativos'))


# ======================================
# ROTA: Editar Ativo
# ======================================
@app.route('/ativos/editar/<int:id>', methods=['POST'])
@login_required
def editar_ativo(id):
    try:
        ativo = Asset.query.get(id)
        if not ativo:
            flash(f"❌ Ativo ID {id} não encontrado.", 'danger')
            return redirect(url_for('ativos'))

        data = request.form.to_dict()
        ativo.brand = data.get('brand', ativo.brand)
        ativo.model = data.get('model', ativo.model)
        ativo.status = data.get('status', ativo.status)
        ativo.notes = data.get('notes', ativo.notes)

        if data.get('cost_center_id') and data['cost_center_id'].isdigit():
            ativo.cost_center_id = int(data['cost_center_id'])
        if data.get('device_user_id') and data['device_user_id'].isdigit():
            ativo.device_user_id = int(data['device_user_id'])
        if data.get('type_id') and data['type_id'].isdigit():
            ativo.type_id = int(data['type_id'])

        db.session.commit()
        flash("✅ Ativo atualizado com sucesso!", "success")
        return redirect(url_for('ativos'))

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao editar ativo: {e}", "danger")
        return redirect(url_for('ativos'))


# ======================================
# ROTA: Excluir Ativo
# ======================================
@app.route('/ativos/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_ativo(id):
    try:
        ativo = Asset.query.get(id)
        if not ativo:
            flash('⚠️ Ativo não encontrado.', 'warning')
            return redirect(url_for('ativos'))

        db.session.delete(ativo)
        db.session.commit()
        flash('🗑️ Ativo excluído com sucesso!', 'success')
        return redirect(url_for('ativos'))

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erro ao excluir ativo: {e}', 'danger')
        return redirect(url_for('ativos'))



@app.route('/ativos/lista')
@login_required
def lista_ativos():
    filtro_tipo = request.args.get('tipo')
    filtro_status = request.args.get('status')
    filtro_cc = request.args.get('cc')

    query = Asset.query

    if filtro_tipo:
        query = query.filter(Asset.asset_type == filtro_tipo)
    if filtro_status:
        query = query.filter(Asset.status == filtro_status)
    if filtro_cc and filtro_cc.isdigit():
        query = query.filter(Asset.cost_center_id == int(filtro_cc))

    ativos = query.order_by(Asset.id.desc()).all()

    centros = {c.id: f"{c.code} - {c.name}" for c in CostCenter.query.all()}
    usuarios = {u.id: f"{u.first_name} {u.last_name}" for u in DeviceUser.query.all()}
    tipos = {t.name: t.name for t in AssetType.query.all()}

    return render_template('lista_ativos.html',
                           ativos=ativos,
                           centros=centros,
                           usuarios=usuarios,
                           tipos=tipos,
                           filtro_tipo=filtro_tipo,
                           filtro_status=filtro_status,
                           filtro_cc=filtro_cc)



@app.route('/usuarios-dispositivo')
@login_required
def usuarios_dispositivo():
    usuarios = DeviceUser.query.order_by(DeviceUser.first_name).all()
    centros = CostCenter.query.all()
    return render_template('usuarios_dispositivo.html', usuarios=usuarios, centros=centros)

@app.route('/usuarios-dispositivo/novo', methods=['GET', 'POST'])
@login_required
def novo_usuario_dispositivo():
    centros = CostCenter.query.order_by(CostCenter.name).all()

    if request.method == 'POST':
        novo = DeviceUser(
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=request.form.get('email'),
            department=request.form.get('department'),
            cost_center_id=request.form.get('cost_center_id')
        )
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('usuarios_dispositivo'))

    return render_template('novo_usuario_dispositivo.html', centros=centros)

@app.route('/centros-de-custo')
@login_required
def centros_de_custo():
    centros = CostCenter.query.order_by(CostCenter.code).all()
    return render_template('centros_de_custo.html', centros=centros)

@app.route('/centros-de-custo/novo', methods=['GET', 'POST'])
@login_required
def novo_centro_de_custo():
    if request.method == 'POST':
        novo = CostCenter(
            name=request.form.get('name'),
            code=request.form.get('code')
        )
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('centros_de_custo'))

    return render_template('novo_centro_de_custo.html')


@app.route('/tipos-dispositivo')
@login_required
def tipos_dispositivo():
    tipos = AssetType.query.order_by(AssetType.name).all()
    return render_template('tipos_dispositivo.html', tipos=tipos)


@app.route('/tipos-dispositivo/novo', methods=['GET', 'POST'])
@login_required
def novo_tipo_dispositivo():
    if request.method == 'POST':
        novo = AssetType(name=request.form.get('name'))
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('tipos_dispositivo'))

    return render_template('novo_tipo_dispositivo.html')


@app.route('/chamados')
@login_required
def chamados_painel():
    # Contagens
    open_count = Ticket.query.filter_by(status='Aberto').count()
    in_progress_count = Ticket.query.filter_by(status='Em Andamento').count()
    closed_count = Ticket.query.filter_by(status='Encerrado').count()

    high_priority = Ticket.query.filter_by(priority='Alta').count()
    medium_priority = Ticket.query.filter_by(priority='Média').count()
    low_priority = Ticket.query.filter_by(priority='Baixa').count()

    last_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()

    # 🧮 Cálculo de SLA (com minutos e congelamento ao encerrar)
    for t in last_tickets:
        if not t.created_at:
            t.sla = {"texto": "—", "cor": "text-muted"}
            continue

        # Se encerrado/cancelado, congela o tempo em updated_at
        fim = t.updated_at if t.status in ['Encerrado', 'Cancelado'] and t.updated_at else datetime.now()
        tempo_decorrido = (fim - t.created_at).total_seconds()

        horas_totais = tempo_decorrido / 3600
        dias = int(horas_totais // 24)
        horas = int(horas_totais % 24)
        minutos = int((tempo_decorrido % 3600) / 60)

        # Monta o texto (1d 3h 42m, 7h 10m, etc.)
        if dias > 0:
            texto_sla = f"{dias}d {horas}h {minutos}m"
        elif horas > 0:
            texto_sla = f"{horas}h {minutos}m"
        else:
            texto_sla = f"{minutos}m"

        # Define cor
        if horas_totais <= 4:
            cor = "text-success fw-bold"   # Verde
        elif horas_totais <= 8:
            cor = "text-warning fw-bold"   # Amarelo
        else:
            cor = "text-danger fw-bold"    # Vermelho

        t.sla = {"texto": texto_sla, "cor": cor}

    # Tempo médio de resolução
    avg_resolution = db.session.query(
        func.avg(text("TIMESTAMPDIFF(MINUTE, tickets.created_at, tickets.updated_at)"))
    ).filter(Ticket.status == 'Encerrado').scalar()

    if avg_resolution:
        avg_seconds = int(avg_resolution * 60)
        avg_days = avg_seconds // (24 * 3600)
        avg_hours = (avg_seconds % (24 * 3600)) // 3600
        avg_minutes = (avg_seconds % 3600) // 60
        avg_time_text = f"{avg_days}d {avg_hours}h {avg_minutes}m"
    else:
        avg_time_text = "N/A"

    return render_template(
        'chamados_painel.html',
        open_count=open_count,
        in_progress_count=in_progress_count,
        closed_count=closed_count,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority,
        avg_resolution=avg_time_text,
        last_tickets=last_tickets
    )


# ✅ Corrige problema de cálculo global que afeta /ativos e outras páginas
@app.context_processor
def inject_dashboard_data():
    try:
        open_count = Ticket.query.filter_by(status='Aberto').count()
        in_progress_count = Ticket.query.filter_by(status='Em Andamento').count()
        closed_count = Ticket.query.filter_by(status='Encerrado').count()

        avg_resolution = db.session.query(
            func.avg(text("TIMESTAMPDIFF(MINUTE, tickets.created_at, tickets.updated_at)"))
        ).filter(Ticket.status == 'Encerrado').scalar()

        if avg_resolution:
            avg_seconds = int(avg_resolution * 60)
            avg_days = avg_seconds // (24 * 3600)
            avg_hours = (avg_seconds % (24 * 3600)) // 3600
            avg_time_text = f"{avg_days}d {avg_hours}h"
        else:
            avg_time_text = "N/A"

        return dict(
            open_count=open_count,
            in_progress_count=in_progress_count,
            closed_count=closed_count,
            avg_resolution=avg_time_text
        )
    except Exception:
        # Evita travar outras páginas se der erro no cálculo
        return dict(
            open_count=0,
            in_progress_count=0,
            closed_count=0,
            avg_resolution="N/A"
        )


@app.context_processor
def inject_datetime():
    from datetime import datetime
    return dict(datetime=datetime)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
