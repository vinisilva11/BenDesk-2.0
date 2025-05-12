from config import Config
import urllib.parse  # ✅ Necessário para codificar a senha com caracteres especiais

class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"

    # 🔐 Senha do banco com caracteres especiais (ex: #, @)
    encoded_password = urllib.parse.quote_plus('#Syn2025@')

    # ✅ String de conexão segura com a senha codificada
    SQLALCHEMY_DATABASE_URI = f'postgresql://admin:{encoded_password}@localhost:5432/bendeskti'
