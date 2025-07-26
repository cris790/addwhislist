import random
import requests
import json
from flask import Flask, request, jsonify
import jwt  # PyJWT

app = Flask(__name__)

# Nome do arquivo com UIDs e passwords
CREDENTIALS_FILE = 'credentials.txt'

def get_random_credentials():
    """Lê um par UID:password aleatório do arquivo de credenciais"""
    with open(CREDENTIALS_FILE, 'r') as f:
        lines = f.readlines()
        if not lines:
            return None, None

        line = random.choice(lines).strip()
        if ':' in line:
            uid, password = line.split(':', 1)
            return uid, password
        return None, None

def decode_jwt(token):
    """Decodifica o token JWT para obter informações da conta"""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        print(f"Erro ao decodificar JWT: {e}")
        return None

@app.route('/add', methods=['GET'])
def add_to_wishlist():
    item_id = request.args.get('id')
    if not item_id:
        return jsonify({"success": False, "message": "ID do item não fornecido"}), 400

    # Passo 1: Pegar credenciais aleatórias
    uid, password = get_random_credentials()
    if not uid or not password:
        return jsonify({"success": False, "message": "Nenhuma credencial disponível"}), 500

    # Passo 2: Obter token JWT
    jwt_url = f"https://genjwt.vercel.app/api/get_jwt?type=4&guest_uid={uid}&guest_password={password}"
    try:
        jwt_response = requests.get(jwt_url)
        jwt_data = jwt_response.json()

        if not jwt_data.get('success'):
            return jsonify({"success": False, "message": "Falha ao obter JWT", "details": jwt_data}), 500

        token = jwt_data['BearerAuth']
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao obter JWT: {str(e)}"}), 500

    # Passo 3: Adicionar à wishlist
    wishlist_url = f"https://dev-wishlist-add.vercel.app/add-wishlist?itemId={item_id}&region=BR&token={token}"
    try:
        wishlist_response = requests.get(wishlist_url)
        wishlist_data = wishlist_response.json()

        if not wishlist_data.get('success'):
            return jsonify({"success": False, "message": "Falha ao adicionar à wishlist", "details": wishlist_data}), 500

        # Passo 4: Decodificar o token e retornar informações
        decoded = decode_jwt(token)
        if not decoded:
            return jsonify({"success": False, "message": "Falha ao decodificar token"}), 500

        return jsonify({
            "success": True,
            "wishlist_response": wishlist_data,
            "account_info": {
                "uid": decoded.get('external_uid'),
                "account_id": decoded.get('account_id'),
                "nickname": decoded.get('nickname')
            },
            "jwt_response": jwt_data
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao adicionar à wishlist: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)