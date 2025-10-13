#!/bin/bash

echo "🚀 Iniciando BenDesk DEV"

cd /home/administrador/BenDesk_DEV || exit 1

source venv/bin/activate

nohup python3 app.py > logs/bendesk_dev_$(date +%F_%H-%M).log 2>&1 &

echo "🟢 BenDesk DEV rodando em segundo plano na porta 5001"
