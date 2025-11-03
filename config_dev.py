# config_dev.py
import os
from urllib.parse import quote_plus

class Config:
    # 🔐 Chave secreta para sessões Flask
    SECRET_KEY = "dev_secret_key"

    # 🗄️ Configuração do banco de dados MySQL (via PyMySQL)
    DB_USER = "root"        # troque se precisar
    DB_PASS = ""            # coloque sua senha se houver
    DB_HOST = "localhost"
    DB_NAME = "bendesk_dev"

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASS)}@{DB_HOST}/{DB_NAME}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 📧 Configurações de e-mail e MSAL (mantidas off em modo dev)
    USE_MSAL = False
    MAIL_ENABLED = False

    # 📨 SMTP (mantém se quiser testar envio local)
    SMTP_USER = "suporteti@synerjet.com"
    SMTP_PASSWORD = "dlplhlxqtygvvlbs"
    SMTP_SERVER = "smtp.office365.com"
    SMTP_PORT = 587

    # 🔄 Configurações Microsoft Graph / IMAP
    EMAIL_ACCOUNT = "suporteti@synerjet.com"
    EMAIL_FOLDER = "Inbox"  # pasta que ele vai monitorar
