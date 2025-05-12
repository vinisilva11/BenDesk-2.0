#!/bin/bash
echo "🔁 Copiando banco de produção para desenvolvimento..."
pg_dump -U admin bendeskti | psql -U admin bendesk_dev
echo "✅ Banco de dados de desenvolvimento atualizado com sucesso!"
