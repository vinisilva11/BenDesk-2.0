from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models.models import db, CostCenter, AssetType, DeviceUser  # ✅ Importa tudo do lugar certo

bp_ativos = Blueprint("ativos", __name__, url_prefix="/ativos")


# ==================================================
# 🏢 CENTROS DE CUSTO - CADASTRAR /EDITAR / EXCLUIR
# ==================================================
@bp_ativos.route("/centros-de-custo")
@login_required
def centros_de_custo():
    centros = CostCenter.query.order_by(CostCenter.created_at.desc()).all()
    return render_template("centros_de_custo.html", centros=centros)


@bp_ativos.route("/centros-de-custo/novo", methods=["POST"])
@login_required
def novo_centro_de_custo():
    code = request.form.get("code")
    name = request.form.get("name")

    if not code or not name:
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for("ativos.centros_de_custo"))

    novo_centro = CostCenter(code=code, name=name)
    db.session.add(novo_centro)
    db.session.commit()

    flash("Centro de custo cadastrado com sucesso!", "success")
    return redirect(url_for("ativos.centros_de_custo"))

@bp_ativos.route("/centros-de-custo/editar/<int:id>", methods=["POST"])
@login_required
def editar_centro_de_custo(id):
    try:
        centro = CostCenter.query.get_or_404(id)
        centro.code = request.form.get("code")
        centro.name = request.form.get("name")

        db.session.commit()
        flash("✅ Centro de custo atualizado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao atualizar centro de custo: {e}", "danger")
    return redirect(url_for("ativos.centros_de_custo"))


@bp_ativos.route("/centros-de-custo/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_centro_de_custo(id):
    try:
        centro = CostCenter.query.get_or_404(id)
        db.session.delete(centro)
        db.session.commit()
        flash("🗑️ Centro de custo excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao excluir centro de custo: {e}", "danger")
    return redirect(url_for("ativos.centros_de_custo"))


# ========================================
# 💻 TIPOS DE DISPOSITIVO
# ========================================
@bp_ativos.route("/tipos-dispositivo")
@login_required
def tipos_dispositivo():
    tipos = AssetType.query.order_by(AssetType.id.desc()).all()
    return render_template("tipos_dispositivo.html", tipos=tipos)


@bp_ativos.route("/tipos-dispositivo/novo", methods=["POST"])
@login_required
def novo_tipo_dispositivo():
    name = request.form.get("name")

    if not name:
        flash("O nome do tipo é obrigatório.", "danger")
        return redirect(url_for("ativos.tipos_dispositivo"))

    novo_tipo = AssetType(name=name)
    db.session.add(novo_tipo)
    db.session.commit()

    flash("Tipo de dispositivo cadastrado com sucesso!", "success")
    return redirect(url_for("ativos.tipos_dispositivo"))


@bp_ativos.route("/tipos-dispositivo/editar/<int:id>", methods=["POST"])
@login_required
def editar_tipo_dispositivo(id):
    tipo = AssetType.query.get_or_404(id)
    name = request.form.get("name")

    if not name:
        flash("O nome do tipo é obrigatório.", "danger")
        return redirect(url_for("ativos.tipos_dispositivo"))

    tipo.name = name
    db.session.commit()

    flash("Tipo de dispositivo atualizado com sucesso!", "success")
    return redirect(url_for("ativos.tipos_dispositivo"))


@bp_ativos.route("/tipos-dispositivo/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_tipo_dispositivo(id):
    tipo = AssetType.query.get_or_404(id)
    db.session.delete(tipo)
    db.session.commit()

    flash(f"Tipo de dispositivo '{tipo.name}' excluído com sucesso!", "success")
    return redirect(url_for("ativos.tipos_dispositivo"))


# ========================================================
# 👤 USUÁRIOS DE DISPOSITIVO - CADASTRAR/ EDITAR / EXCLUIR
# ========================================================
@bp_ativos.route("/usuarios-dispositivo")
@login_required
def usuarios_dispositivo():
    usuarios = DeviceUser.query.order_by(DeviceUser.first_name.asc()).all()
    centros = CostCenter.query.all()
    return render_template("usuarios_dispositivo.html", usuarios=usuarios, centros=centros)


@bp_ativos.route("/usuarios-dispositivo/novo", methods=["POST"])
@login_required
def novo_usuario_dispositivo():
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    department = request.form.get("department")
    cost_center_id = request.form.get("cost_center_id")

    if not first_name or not email:
        flash("Preencha os campos obrigatórios: nome e e-mail.", "danger")
        return redirect(url_for("ativos.usuarios_dispositivo"))

    novo_usuario = DeviceUser(
        first_name=first_name,
        last_name=last_name,
        email=email,
        department=department,
        cost_center_id=cost_center_id
    )

    db.session.add(novo_usuario)
    db.session.commit()

    flash("Usuário cadastrado com sucesso!", "success")
    return redirect(url_for("ativos.usuarios_dispositivo"))


@bp_ativos.route("/usuarios-dispositivo/editar/<int:id>", methods=["POST"])
@login_required
def editar_usuario_dispositivo(id):
    try:
        usuario = DeviceUser.query.get_or_404(id)
        usuario.first_name = request.form.get("first_name")
        usuario.last_name = request.form.get("last_name")
        usuario.email = request.form.get("email")
        usuario.department = request.form.get("department")
        usuario.cost_center_id = request.form.get("cost_center_id") or None

        db.session.commit()
        flash("✅ Usuário atualizado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao atualizar usuário: {e}", "danger")
    return redirect(url_for("ativos.usuarios_dispositivo"))


@bp_ativos.route("/usuarios-dispositivo/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_usuario_dispositivo(id):
    try:
        usuario = DeviceUser.query.get_or_404(id)
        db.session.delete(usuario)
        db.session.commit()
        flash("🗑️ Usuário excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao excluir usuário: {e}", "danger")
    return redirect(url_for("ativos.usuarios_dispositivo"))

