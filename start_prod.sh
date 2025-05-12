#!/bin/bash
echo "🚀 Iniciando ambiente de PRODUÇÃO"
export FLASK_ENV=production
python3 app.py --host=0.0.0.0 --port=5001
