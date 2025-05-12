#!/bin/bash
echo "🚀 Iniciando ambiente de DESENVOLVIMENTO"
export FLASK_ENV=development
python3 app.py --host=0.0.0.0 --port=5000
