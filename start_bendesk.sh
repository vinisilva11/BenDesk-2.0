#!/bin/bash

# Caminho para o diretório do projeto
PROJECT_DIR="/home/administrador/BenDesk"

# Nome do ambiente virtual
VENV_DIR="$PROJECT_DIR/venv"

# Entrar na pasta do projeto
cd "$PROJECT_DIR" || { echo "❌ Falha ao acessar a pasta do projeto"; exit 1; }

# Ativar o ambiente virtual
if [ -d "$VENV_DIR" ]; then
    echo "✅ Ativando o ambiente virtual..."
    source "$VENV_DIR/bin/activate"
else
    echo "⚠️ Ambiente virtual não encontrado. Criando um novo..."
    python3 -m venv venv
    source "$VENV_DIR/bin/activate"
    echo "🔧 Instalando dependências..."
    pip install -r requirements.txt
fi

# Verifica argumento: 'dev' ou 'prod' (padrão)
if [ "$1" == "dev" ]; then
    echo "🔧 Modo: DESENVOLVIMENTO"
    export FLASK_ENV=development
    export BENDESK_DB_NAME=bendesk_dev
else
    echo "🚀 Modo: PRODUÇÃO"
    export FLASK_ENV=production
    export BENDESK_DB_NAME=bendeskti
fi

# Inicia o app em segundo plano
nohup python3 app.py > logs/bendesk_$(date +%F_%H-%M).log 2>&1 &
echo "🟢 BenDesk iniciado em segundo plano. Log: logs/bendesk_<data>.log"
