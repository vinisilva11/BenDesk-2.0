import requests
import json
from datetime import datetime, timezone, timedelta
from models.models import db, Ticket, TicketComment, TicketAttachment
from flask import Flask
import os
import base64
import re  # regex
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ===========================================================
#  CONFIGURAÇÃO DO AMBIENTE
# ===========================================================
try:
    from config_dev import Config  # 🧩 Ambiente local (DEV)
except ImportError:
    from config import Config      # ☁️ Produção (Linux)

# Flag pra saber se é DEV
IS_DEV = hasattr(Config, "USE_MSAL") and Config.USE_MSAL is False

# Flask app só pra usar o db (quando rodar esse arquivo isolado)
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# SMTP (Microsoft 365 / Outlook)
SMTP_USER = Config.SMTP_USER
SMTP_PASSWORD = Config.SMTP_PASSWORD
SMTP_SERVER = Config.SMTP_SERVER
SMTP_PORT = Config.SMTP_PORT

UPLOAD_FOLDER = 'uploads'


# ===========================================================
#  MODO DEV — TUDO “FAKE”
# ===========================================================
if IS_DEV:
    print("🧩 Rodando em modo DEV — MSAL e SMTP desativados.")

    def get_access_token():
        print("🔒 [DEV] MSAL desativado.")
        return None

    def fetch_unread_emails(_):
        print("📭 [DEV] Nenhum e-mail será buscado.")
        return []

    def send_confirmation_email(*args, **kwargs):
        print("📨 [DEV] E-mail de confirmação simulado.")

    def send_update_email(*args, **kwargs):
        print("📨 [DEV] E-mail de atualização simulado.")

    def mark_email_as_read(*args, **kwargs):
        print("📬 [DEV] Marcação de e-mail desativada.")

    def save_attachments(*args, **kwargs):
        print("📎 [DEV] Salvamento de anexos desativado.")

    def process_emails():
        print("🚫 [DEV] Processamento de e-mails desativado.")

# ===========================================================
#  MODO PRODUÇÃO — TUDO ATIVO
# ===========================================================
else:
    from msal import ConfidentialClientApplication

    # Microsoft Graph API setup
    TENANT_ID = '2ba5c794-0c81-4937-b0bb-756c39ad2499'
    CLIENT_ID = '7039355e-5123-4b5f-986c-1839d915e8b1'
    CLIENT_SECRET = 'p1n8Q~T.MGCTpsAndADASvTD9YUxZH6qZ1T-cdaE'
    USER_EMAIL = 'suporteti@synerjet.com'

    AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
    SCOPE = ['https://graph.microsoft.com/.default']
    GRAPH_ENDPOINT = 'https://graph.microsoft.com/v1.0'

    # -----------------------------
    #  TOKEN MSAL
    # -----------------------------
    def get_access_token():
        app_auth = ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET
        )
        token_response = app_auth.acquire_token_for_client(scopes=SCOPE)
        return token_response.get('access_token')

    # -----------------------------
    #  BUSCAR EMAILS NÃO LIDOS
    # -----------------------------
    def fetch_unread_emails(access_token):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f'{GRAPH_ENDPOINT}/users/{USER_EMAIL}/mailFolders/Inbox/messages?$filter=isRead eq false'
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('value', [])
        else:
            print(f"Erro ao buscar e-mails: {response.status_code} - {response.text}")
            return []

    # -----------------------------
    #  LIMPAR CORPO DO EMAIL
    # -----------------------------
    def clean_email_body(body: str) -> str:
        """Remove assinatura, rodapé e texto repetido."""
        if not body:
            return ""

        if '--- Responda acima desta linha ---' in body:
            body = body.split('--- Responda acima desta linha ---')[0].strip()

        signature_patterns = [
            r'Atenciosamente.*',
            r'Enviado do meu.*',
            r'--\s*$',
        ]
        for pattern in signature_patterns:
            body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.DOTALL).strip()
        return body

    # -----------------------------
    #  CRIAR TICKET OU COMENTÁRIO
    # -----------------------------
    def create_ticket_or_comment_from_email(email):
        subject = email.get('subject', 'Sem Assunto')
        body = email.get('body', {}).get('content', '').strip()
        sender_email = email.get('from', {}).get('emailAddress', {}).get('address', '')
        sender_name = email.get('from', {}).get('emailAddress', {}).get('name', '')
        received_time = email.get('receivedDateTime')

        if received_time:
            created_time = datetime.strptime(received_time, '%Y-%m-%dT%H:%M:%S%z')
            created_time = created_time.astimezone(timezone(timedelta(hours=-3)))  # 🇧🇷 UTC-3
            created_time = created_time.replace(tzinfo=None)
        else:
            created_time = datetime.utcnow()

        ticket_match = re.search(r'\[#(\d+)\]', subject)

        with app.app_context():
            # Se assunto tem [#ID], vira comentário do ticket
            if ticket_match:
                ticket_id = int(ticket_match.group(1))
                ticket = Ticket.query.filter_by(id=ticket_id).first()

                if ticket:
                    cleaned_comment = clean_email_body(body)
                    if cleaned_comment:
                        new_comment = TicketComment(
                            ticket_id=ticket.id,
                            commenter=sender_name or sender_email,
                            comment=cleaned_comment
                        )
                        db.session.add(new_comment)
                        db.session.commit()

                    save_attachments(email['id'], ticket.id, get_access_token())
                    ticket.updated_at = created_time
                    db.session.commit()
                    return

                # Se não achou ticket mas o assunto tem ID, ignora criar novo
                recent_ticket = Ticket.query.filter(
                    Ticket.requester_email == sender_email,
                    Ticket.title == subject,
                    Ticket.created_at >= datetime.utcnow() - timedelta(hours=2)
                ).first()

                if recent_ticket:
                    print(f"⚠️ Ticket duplicado detectado — ignorando criação: {subject}")
                return

            # 🚨 Cria novo ticket se não houver match
            new_ticket = Ticket(
                title=subject,
                description=body,
                status='Aberto',
                priority='Média',
                requester_email=sender_email,
                requester_name=sender_name,
                created_at=created_time,
                updated_at=created_time
            )
            db.session.add(new_ticket)
            db.session.commit()

            print(f"📥 Novo ticket criado automaticamente a partir de {sender_email}, sem envio de confirmação.")

            # Salva anexos normalmente
            save_attachments(email['id'], new_ticket.id, get_access_token())

    # =======================================================
    #  ENVIO DE EMAIL — CONFIRMAÇÃO
    # =======================================================
    def send_confirmation_email(ticket, recipient_email, recipient_name):
        subject = f"Chamado Recebido - Ticket [#{ticket.id}]"
        body_html = f"""
<p>Olá <b>{recipient_name or recipient_email}</b>,</p>

<p>Recebemos sua solicitação com sucesso.</p>

<p>
✅ Número do ticket: <b>[#{ticket.id}]</b><br>
📝 Título: <b>{ticket.title}</b>
</p>

<p>Em breve, nossa equipe entrará em contato.</p>

<p style="color:#777;font-size:12px;">
E-mail automático, por favor NÃO responder.
</p>
"""

        msg = MIMEMultipart("alternative")
        msg['From'] = SMTP_USER
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
                print(f"Confirmação enviada para {recipient_email}")
        except Exception as e:
            print(f"Erro ao enviar confirmação: {e}")

    # =======================================================
    #  ENVIO DE EMAIL — ATUALIZAÇÃO / ENCERRAMENTO
    # =======================================================
    def send_update_email(ticket, recipient_email, recipient_name, subject_extra, body_html, body_text=None):
        """
        Envia e-mail multipart (texto + HTML) compatível com Outlook.
        Assinatura bate com o que você usa no app.py:
        send_update_email(ticket, email, nome, subject_extra, body_html, body_text)
        """
        subject = f"[Atualização Ticket [#{ticket.id}]] {ticket.title} - {subject_extra}"

        msg = MIMEMultipart("alternative")
        msg['From'] = SMTP_USER
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Texto simples (fallback) – se você mandar body_text no app.py, ele entra aqui
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

        # HTML bonito vindo pronto do app.py
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, recipient_email, msg.as_string())

            print(f"📨 E-mail de atualização enviado para {recipient_email}")
        except Exception as e:
            print(f"❌ Erro ao enviar atualização: {e}")

    # =======================================================
    #  MARCAR E-MAIL COMO LIDO
    # =======================================================
    def mark_email_as_read(email_id, access_token):
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        url = f'{GRAPH_ENDPOINT}/users/{USER_EMAIL}/messages/{email_id}'
        data = {'isRead': True}
        response = requests.patch(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            print(f"E-mail {email_id} marcado como lido.")
        else:
            print(f"Erro ao marcar como lido: {response.status_code} - {response.text}")

    # =======================================================
    #  PROCESSAR E-MAILS
    # =======================================================
    def process_emails():
        token = get_access_token()
        emails = fetch_unread_emails(token)
        print(f"Encontrados {len(emails)} e-mails não lidos.")
        for email in emails:
            # Marca como lido primeiro
            mark_email_as_read(email['id'], token)
            create_ticket_or_comment_from_email(email)

    # =======================================================
    #  SALVAR ANEXOS
    # =======================================================
    def save_attachments(email_id, ticket_id, access_token):
        headers = {'Authorization': f'Bearer {access_token}'}
        attachments_url = f"{GRAPH_ENDPOINT}/users/{USER_EMAIL}/messages/{email_id}/attachments"
        response = requests.get(attachments_url, headers=headers)
        if response.status_code == 200:
            attachments = response.json().get('value', [])
            for attachment in attachments:
                if attachment.get('@odata.type') == '#microsoft.graph.fileAttachment':
                    filename = attachment['name']
                    content_bytes = attachment['contentBytes']
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(content_bytes))
                    with app.app_context():
                        new_attachment = TicketAttachment(
                            ticket_id=ticket_id,
                            filename=filename,
                            filepath=filepath
                        )
                        db.session.add(new_attachment)
                        db.session.commit()
                    print(f"Anexo salvo: {filename}")
        else:
            print(f"Erro ao buscar anexos: {response.status_code} - {response.text}")


# ===========================================================
#  EXECUÇÃO DIRETA (rodar processamento de e-mails)
# ===========================================================
if __name__ == '__main__':
    if IS_DEV:
        print("🚫 MSAL e processamento de e-mails desativados no ambiente DEV.")
    else:
        process_emails()
