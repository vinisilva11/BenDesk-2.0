from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pytz

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    profile = db.Column(db.String(20), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    email = db.Column(db.String(100), nullable=True)

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Aberto')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')), onupdate=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))
    requester_email = db.Column(db.String(100))
    requester_name = db.Column(db.String(100))
    assigned_to = db.Column(db.String(100))
    priority = db.Column(db.String(20), default='Média')

class TicketHistory(db.Model):
    __tablename__ = 'ticket_history'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    changed_by = db.Column(db.String(100))
    change_description = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    commenter = db.Column(db.String(100))
    comment = db.Column(db.Text, nullable=False)
    commented_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class TicketAttachment(db.Model):
    __tablename__ = 'ticket_attachments'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    filename = db.Column(db.String(255))
    filepath = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))

#Inicio do codigo para tela de Ativos

class CostCenter(db.Model):
    __tablename__ = 'cost_centers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))

class DeviceUser(db.Model):
    __tablename__ = 'device_users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(150))
    department = db.Column(db.String(100))
    cost_center_id = db.Column(db.Integer, db.ForeignKey('cost_centers.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))

class AssetType(db.Model):
    __tablename__ = 'asset_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)    

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.String(100), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('asset_types.id'))
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    hostname = db.Column(db.String(100))
    invoice_number = db.Column(db.String(50))
    serial_number = db.Column(db.String(100), unique=True)
    patrimony_code = db.Column(db.String(50))
    status = db.Column(db.String(50))
    ownership = db.Column(db.String(20))  # Próprio / Locado
    location = db.Column(db.String(100))
    cost_center_id = db.Column(db.Integer, db.ForeignKey('cost_centers.id'))
    device_user_id = db.Column(db.Integer, db.ForeignKey('device_users.id'))
    acquisition_date = db.Column(db.Date)
    return_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))

# Final do codigo para tela de ativos

#Inicio da Class dos estoques    
# ✅ Tabela de itens em estoque
class EstoqueItem(db.Model):
    __tablename__ = 'estoque_itens'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    quantidade = db.Column(db.Float, default=0)
    unidade = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))

# ✅ Tabela de movimentações (entradas/saídas)
class EstoqueMovimentacao(db.Model):
    __tablename__ = 'estoque_movimentacoes'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20))  # entrada ou saida
    item_id = db.Column(db.Integer, db.ForeignKey('estoque_itens.id'), nullable=False)
    item = db.relationship('EstoqueItem', backref='movimentacoes')
    quantidade = db.Column(db.Float)
    descricao = db.Column(db.String(255))
    usuario = db.Column(db.String(100))  # Nome ou username do usuário que realizou
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))

# Final do codigo para Class dos estoques•µ   