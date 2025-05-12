import requests
import json
from datetime import datetime, timezone
from msal import ConfidentialClientApplication
from models.models import db, Ticket, TicketComment, TicketAttachment
from config import Config
from flask import Flask
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import base64
import re  # ✅ regex

# Configuração do SMTP (Microsoft 365 / Outlook)
SMTP_USER = Config.SMTP_USER
SMTP_PASSWORD = Config.SMTP_PASSWORD
SMTP_SERVER = Config.SMTP_SERVER
SMTP_PORT = Config.SMTP_PORT

# Config Flask app (para usar o SQLAlchemy)
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Microsoft Graph API setup
TENANT_ID = '2ba5c794-0c81-4937-b0bb-756c39ad2499'
CLIENT_ID = '7039355e-5123-4b5f-986c-1839d915e8b1'
CLIENT_SECRET = 'p1n8Q~T.MGCTpsAndADASvTD9YUxZH6qZ1T-cdaE'
USER_EMAIL = 'suporteti@synerjet.com'

AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
SCOPE = ['https://graph.microsoft.com/.default']
GRAPH_ENDPOINT = 'https://graph.microsoft.com/v1.0'

def get_access_token():
    app_auth = ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )
    token_response = app_auth.acquire_token_for_client(scopes=SCOPE)
    return token_response.get('access_token')

def fetch_unread_emails(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    url = f'{GRAPH_ENDPOINT}/users/{USER_EMAIL}/mailFolders/Inbox/messages?$filter=isRead eq false'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        print(f"Erro ao buscar e-mails: {response.status_code} - {response.text}")
        return []

def clean_email_body(body):
    """
    Pega somente o conteúdo acima da linha delimitadora e remove assinaturas comuns.
    """
    # 👉 Cortar só até a linha delimitadora (se existir)
    if '--- Responda acima desta linha ---' in body:
        body = body.split('--- Responda acima desta linha ---')[0].strip()

    # 🔎 Limpar assinaturas padrão (simples)
    # Remove tudo após "Atenciosamente" ou "Enviado do meu"
    signature_patterns = [
        r'Atenciosamente.*',
        r'Enviado do meu.*',
        r'--\s*$',  # padrão de assinatura
    ]
    for pattern in signature_patterns:
        body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.DOTALL).strip()

    return body

def create_ticket_or_comment_from_email(email):
    subject = email.get('subject', 'Sem Assunto')
    body = email.get('body', {}).get('content', '').strip()
    sender_email = email.get('from', {}).get('emailAddress', {}).get('address', '')
    sender_name = email.get('from', {}).get('emailAddress', {}).get('name', '')
    received_time = email.get('receivedDateTime')    
    if received_time:
        created_time = datetime.strptime(received_time, '%Y-%m-%dT%H:%M:%S%z')
        created_time = created_time.astimezone(timezone.utc).replace(tzinfo=None)  # 👉 converte para UTC puro
        print(f"🕒 Recebido: {received_time}, Interpretado: {created_time}")  # ✅ debug opcional
    else:
        created_time = datetime.utcnow()  # fallback seguro
        print(f"⚠️ Sem data recebida, usando agora: {created_time}")

    ticket_match = re.search(r'\[#(\d+)\]', subject)

    with app.app_context():
        if ticket_match:
            ticket_id = int(ticket_match.group(1))
            ticket = Ticket.query.filter_by(id=ticket_id).first()

            if ticket:
                # ✅ Pega só a parte relevante
                cleaned_comment = clean_email_body(body)

                if cleaned_comment:
                    new_comment = TicketComment(
                        ticket_id=ticket.id,
                        commenter=sender_name or sender_email,
                        comment=cleaned_comment
                    )
                    db.session.add(new_comment)
                    db.session.commit()
                    print(f"✅ Comentário adicionado ao ticket #{ticket_id}")

                # ✅ Também salva o email completo como histórico oculto (opcional)
                # Se quiser logar o corpo completo para auditoria:
                # new_comment_full = TicketComment(
                #     ticket_id=ticket.id,
                #     commenter='[LOG]',
                #     comment=body
                # )
                # db.session.add(new_comment_full)

                # Salvar anexos
                save_attachments(email['id'], ticket.id, get_access_token())

                # ✅ Atualizar timestamp
                ticket.updated_at = created_time
                db.session.commit()

                return
            else:
                print(f"⚠️ Ticket #{ticket_id} não encontrado. Criando novo ticket.")

        # 🚨 Criação de novo ticket (comportamento padrão)
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
        print(f"✅ Novo ticket criado: {subject}")

        # Enviar confirmação
        send_confirmation_email(new_ticket, sender_email, sender_name)

        # Salvar anexos
        save_attachments(email['id'], new_ticket.id, get_access_token())

def send_confirmation_email(ticket, recipient_email, recipient_name):
    subject = f"Chamado Recebido - Ticket [#{ticket.id}]"
    body = f"""
Olá {recipient_name or recipient_email},

**E-mail automático, por favor NÃO responder**

Recebemos sua solicitação com sucesso.

✅ Número do ticket: [#{ticket.id}]
📝 Título: {ticket.title}

Em breve, nossa equipe entrará em contato.

--- Responda acima desta linha ---

Atenciosamente,
Equipe de TI - Synerjet
"""

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Confirmação enviada para {recipient_email}")
    except Exception as e:
        print(f"Erro ao enviar confirmação: {e}")

def send_update_email(ticket, recipient_email, recipient_name, subject_extra, body_message):
    subject = f"[Atualização Ticket [#{ticket.id}]] {ticket.title} - {subject_extra}"
    body = f"""
Olá {recipient_name or recipient_email},

Seu ticket foi atualizado.

✅ Número do ticket: [#{ticket.id}]
📝 Título: {ticket.title}

{body_message}

--- Responda acima desta linha ---

Para mais detalhes, entre em contato conosco.

Atenciosamente,
Equipe de TI - Synerjet
"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipient_email, msg.as_string())

        print(f"E-mail de atualização enviado para {recipient_email}")
    except Exception as e:
        print(f"Erro ao enviar atualização: {e}")

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

def process_emails():
    token = get_access_token()
    emails = fetch_unread_emails(token)
    print(f"Encontrados {len(emails)} e-mails não lidos.")
    for email in emails:
        create_ticket_or_comment_from_email(email)
        mark_email_as_read(email['id'], token)

UPLOAD_FOLDER = 'uploads'

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

if __name__ == '__main__':
    process_emails()
