from config import Config

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"
    SQLALCHEMY_DATABASE_URI = 'postgresql://admin:admin@localhost/bendesk_dev'
