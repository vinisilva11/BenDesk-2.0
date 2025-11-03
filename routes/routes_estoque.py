from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models.models import db, EstoqueItem, EstoqueMovimentacao

estoque_bp = Blueprint('estoque', __name__)

# 📦 Página principal do estoque
@estoque_bp.route('/estoque')
@login_required
def estoque():
    materiais = EstoqueItem.query.order_by(EstoqueItem.nome).all()

    categorias_data = {}
    for m in materiais:
        if m.categoria:
            categorias_data[m.categoria] = categorias_data.get(m.categoria, 0) + 1
        else:
            categorias_data["Sem Categoria"] = categorias_data.get("Sem Categoria", 0) + 1

    entradas = EstoqueMovimentacao.query.filter_by(tipo='entrada').count()
    saidas = EstoqueMovimentacao.query.filter_by(tipo='saida').count()
    historico = EstoqueMovimentacao.query.order_by(EstoqueMovimentacao.timestamp.desc()).limit(20).all()

    return render_template(
        'estoque.html',
        itens=materiais,
        categorias_data=categorias_data,
        entradas=entradas,
        saidas=saidas,
        historico=historico
    )


# ➕ Cadastro de novo material
@estoque_bp.route('/estoque/novo', methods=['GET', 'POST'])
@login_required
def novo_material():
    if request.method == 'POST':
        nome = request.form.get('nome')
        categoria = request.form.get('categoria')
        categoria_nova = request.form.get('categoria_nova')
        if categoria_nova:
            categoria = categoria_nova.strip()
        unidade = request.form.get('unidade')
        quantidade = float(request.form.get('quantidade') or 0)
        observacoes = request.form.get('observacoes')

        novo_item = EstoqueItem(
            nome=nome,
            categoria=categoria,
            unidade=unidade,
            quantidade=quantidade
        )

        # ✅ Define status inicial
        if quantidade <= 0:
            novo_item.status = 'Reservado'
        elif quantidade <= 5:
            novo_item.status = 'Baixo Estoque'
        else:
            novo_item.status = 'Disponível'

        db.session.add(novo_item)
        db.session.flush()  # força geração do ID

        movimento = EstoqueMovimentacao(
            tipo='entrada',
            item_id=novo_item.id,
            quantidade=quantidade,
            descricao=observacoes or 'Entrada de material',
            usuario=current_user.username
        )
        db.session.add(movimento)
        db.session.commit()

        flash('✅ Material cadastrado e entrada registrada com sucesso!', 'success')
        return redirect(url_for('estoque.estoque'))
    
    categorias_existentes = sorted({i.categoria for i in EstoqueItem.query.all() if i.categoria})
    return render_template('novo_item.html', categorias=categorias_existentes)


# 🔄 Entrada de material existente (reposição)
@estoque_bp.route('/estoque/entrada', methods=['POST'])
@login_required
def entrada_estoque():
    item_id = request.form.get('item_id')
    quantidade = float(request.form.get('quantidade') or 0)
    observacoes = request.form.get('observacoes')

    item = EstoqueItem.query.get(item_id)

    if not item:
        flash('⚠️ Erro: item não encontrado.', 'danger')
        return redirect(url_for('estoque.estoque'))

    # Atualiza a quantidade do estoque
    item.quantidade += quantidade

    # ✅ Atualiza status automaticamente (reposição)
    if item.quantidade <= 0:
        item.status = 'Reservado'
    elif item.quantidade <= 5:
        item.status = 'Baixo Estoque'
    else:
        item.status = 'Disponível'

    movimento = EstoqueMovimentacao(
        tipo='entrada',
        item_id=item.id,
        quantidade=quantidade,
        descricao=observacoes or 'Reposição de material',
        usuario=current_user.username
    )
    db.session.add(movimento)
    db.session.commit()

    flash('✅ Entrada registrada e status atualizado!', 'success')
    return redirect(url_for('estoque.estoque'))


# ➖ Saída de material
@estoque_bp.route('/estoque/saida', methods=['POST'])
@login_required
def saida_estoque():
    item_id = request.form.get('item_id')
    quantidade = float(request.form.get('quantidade') or 0)
    responsavel = request.form.get('responsavel')
    observacoes = request.form.get('observacoes')

    item = EstoqueItem.query.get(item_id)

    if not item:
        flash('⚠️ Erro: item não encontrado.', 'danger')
        return redirect(url_for('estoque.estoque'))

    if item.quantidade < quantidade:
        flash('⚠️ Quantidade insuficiente em estoque.', 'danger')
        return redirect(url_for('estoque.estoque'))

    item.quantidade -= quantidade

    # ✅ Atualiza status após saída
    if item.quantidade <= 0:
        item.status = 'Reservado'
    elif item.quantidade <= 5:
        item.status = 'Baixo Estoque'
    else:
        item.status = 'Disponível'

    movimento = EstoqueMovimentacao(
        tipo='saida',
        item_id=item.id,
        quantidade=quantidade,
        descricao=f"{observacoes or ''} (Responsável: {responsavel})",
        usuario=current_user.username
    )
    db.session.add(movimento)
    db.session.commit()

    flash('✅ Saída registrada e status atualizado!', 'success')
    return redirect(url_for('estoque.estoque'))


# 📜 Histórico de movimentações
@estoque_bp.route('/estoque/historico')
@login_required
def historico_estoque():
    historico = EstoqueMovimentacao.query.order_by(EstoqueMovimentacao.timestamp.desc()).all()
    return render_template('historico_estoque.html', historico=historico)


# 🧾 Lista completa de estoque (com filtros)
@estoque_bp.route('/estoque/lista')
@login_required
def lista_estoque():
    filtro_categoria = request.args.get('categoria')
    filtro_status = request.args.get('status')

    query = EstoqueItem.query
    if filtro_categoria:
        query = query.filter(EstoqueItem.categoria == filtro_categoria)
    if filtro_status:
        query = query.filter(EstoqueItem.status == filtro_status)

    itens = query.order_by(EstoqueItem.nome.asc()).all()
    categorias = sorted({i.categoria for i in EstoqueItem.query.all() if i.categoria})

    return render_template(
        'lista_estoque.html',
        itens=itens,
        categorias=categorias,
        filtro_categoria=filtro_categoria,
        filtro_status=filtro_status
    )


# ✏️ Editar item
@estoque_bp.route('/estoque/editar/<int:id>', methods=['POST'])
@login_required
def editar_item(id):
    item = EstoqueItem.query.get_or_404(id)
    data = request.form
    item.nome = data.get('nome')
    item.categoria = data.get('categoria')
    item.unidade = data.get('unidade')
    item.quantidade = float(data.get('quantidade') or 0)

    # ✅ Atualiza status após edição
    if item.quantidade <= 0:
        item.status = 'Reservado'
    elif item.quantidade <= 5:
        item.status = 'Baixo Estoque'
    else:
        item.status = 'Disponível'

    db.session.commit()
    flash('✅ Item atualizado com sucesso!', 'success')
    return redirect(url_for('estoque.estoque'))


# 🗑️ Excluir item
@estoque_bp.route('/estoque/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_item(id):
    item = EstoqueItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('🗑️ Item excluído com sucesso!', 'success')
    return redirect(url_for('estoque.estoque'))
