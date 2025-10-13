from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required
from models.models import db, DeviceUser, CostCenter

usuarios_dispositivo_bp = Blueprint('usuarios_dispositivo', __name__)

@usuarios_dispositivo_bp.route('/usuarios-dispositivo')
@login_required
def listar_usuarios_dispositivo():
    usuarios = DeviceUser.query.order_by(DeviceUser.first_name).all()
    centros = CostCenter.query.all()
    return render_template('usuarios_dispositivo.html', usuarios=usuarios, centros=centros)

@usuarios_dispositivo_bp.route('/usuarios-dispositivo/editar/<int:id>', methods=['PUT'])
@login_required
def editar_usuario_dispositivo(id):
    usuario = DeviceUser.query.get_or_404(id)
    data = request.get_json()

    usuario.first_name = data.get('first_name')
    usuario.last_name = data.get('last_name')
    usuario.email = data.get('email')
    usuario.department = data.get('department')
    usuario.cost_center_id = data.get('cost_center_id')

    db.session.commit()
    return jsonify({'success': True})

@usuarios_dispositivo_bp.route('/usuarios-dispositivo/excluir/<int:id>', methods=['DELETE'])
@login_required
def excluir_usuario_dispositivo(id):
    usuario = DeviceUser.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    return jsonify({'success': True})
