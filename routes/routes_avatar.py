# routes_avatar.py
from flask import Blueprint, send_file, abort
from io import BytesIO
import requests
import os
from datetime import datetime, timedelta

# Dados do app registrado no Microsoft Azure
CLIENT_ID = "d5fcee84-da14-4a5a-bf95-9357554a11ce"
TENANT_ID = "2ba5c794-0c81-4937-b0bb-756c39ad2499"
CLIENT_SECRET = "Ekz8Q~nuAiCUk~svnj8tWiMyKCxs46XYjXcjUdc0"

# Blueprint para rota de avatar
avatar_bp = Blueprint("avatar", __name__)

# Cache de token para evitar múltiplas chamadas
_token_cache = {
    "access_token": None,
    "expires_at": datetime.utcnow()
}

def get_token():
    if _token_cache["access_token"] and datetime.utcnow() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        token_data = response.json()
        _token_cache["access_token"] = token_data["access_token"]
        _token_cache["expires_at"] = datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))
        return token_data["access_token"]
    else:
        raise Exception("Erro ao obter token do Microsoft Graph")

@avatar_bp.route("/avatar/<email>")
def avatar(email):
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "image/jpg"
    }
    url = f"https://graph.microsoft.com/v1.0/users/{email}/photo/$value"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return send_file(BytesIO(response.content), mimetype='image/jpeg')
    else:
        # Pode ajustar para imagem default
        abort(404, description="Imagem não encontrada")
