import os

# Configuração básica para rodar localmente
class Config:
    SECRET_KEY = "dev_secret_key"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root@localhost/bendesk_dev"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Desativando MSAL e envio de email em modo dev
    USE_MSAL = False
    MAIL_ENABLED = False
