import os

class Config:
    SECRET_KEY = 'sua_chave_secreta_aqui'

    # Usa a variável de ambiente BENDESK_DB_NAME para selecionar o banco
    DB_NAME = os.getenv("BENDESK_DB_NAME", "bendeskti")
    SQLALCHEMY_DATABASE_URI = f"postgresql://admin:admin@localhost:5432/{DB_NAME}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SMTP Configurações
    SMTP_USER = 'suporteti@synerjet.com'
    SMTP_PASSWORD = 'dlplhlxqtygvvlbs'
    SMTP_SERVER = 'smtp.office365.com'
    SMTP_PORT = 587