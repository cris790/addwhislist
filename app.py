from flask import Flask, request, jsonify
import requests
import json
import ChangeWishListItem_pb2 as wishlist_pb2
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict
import jwt
from datetime import datetime

app = Flask(__name__)

# Chave AES e IV
KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# Token fixo (coloque seu JWT válido aqui)
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInN2ciI6IjIiLCJ0eXAiOiJKV1QifQ.eyJhY2NvdW50X2lkIjoxMTA2MjkxMDY1Nywibmlja25hbWUiOiJUSFVHX2RLNGJPdGgiLCJub3RpX3JlZ2lvbiI6IkJSIiwibG9ja19yZWdpb24iOiJCUiIsImV4dGVybmFsX2lkIjoiZWZjNDFkZjMwMmZlYzc1ZmM2ZjIxNTUzYzMwNjE4NTEiLCJleHRlcm5hbF90eXBlIjo0LCJwbGF0X2lkIjoxLCJjbGllbnRfdmVyc2lvbiI6IjEuMTExLjEiLCJlbXVsYXRvcl9zY29yZSI6MTAwLCJpc19lbXVsYXRvciI6dHJ1ZSwiY291bnRyeV9jb2RlIjoiVVMiLCJleHRlcm5hbF91aWQiOjM3NDMzMjcwNTQsInJlZ19hdmF0YXIiOjEwMjAwMDAwNywic291cmNlIjowLCJsb2NrX3JlZ2lvbl90aW1lIjoxNzM4OTcyOTY0LCJjbGllbnRfdHlwZSI6Miwic2lnbmF0dXJlX21kNSI6IiIsInVzaW5nX3ZlcnNpb24iOjAsInJlbGVhc2VfY2hhbm5lbCI6IiIsInJlbGVhc2VfdmVyc2lvbiI6Ik9CNTAiLCJleHAiOjE3NTM5MTYwNDN9.4Yc8kuzHVLwRV7ZTbr3dDJ3MnnBgK7o6LIhIaaVv4s8"

def decode_jwt(token):
    try:
        # Decodifica o JWT sem verificar a assinatura (pois não temos a chave secreta)
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        return {"error": f"Erro ao decodificar JWT: {str(e)}"}

def build_encrypted_wishlist_data(add_item_ids, del_item_ids):
    req = wishlist_pb2.CSChangeWishListItemReq()

    if add_item_ids:
        ids = list(map(int, add_item_ids.split(',')))
        req.add_item_ids.extend(ids)
        req.add_source.extend(["default"] * len(ids))

    if del_item_ids:
        ids = list(map(int, del_item_ids.split(',')))
        req.del_item_ids.extend(ids)
        req.del_source.extend(["default"] * len(ids))

    serialized_data = req.SerializeToString()
    padded_data = pad(serialized_data, AES.block_size)
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    encrypted_data = cipher.encrypt(padded_data)
    return encrypted_data

def send_wishlist_request(encrypted_data):
    url = "https://client.us.freefiremobile.com/ChangeWishListItem"
    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {JWT_TOKEN}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB50",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; SM-M526B Build/TP1A.220624.014)",
        "Host": "client.us.freefiremobile.com",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip"
    }

    return requests.post(url, headers=headers, data=encrypted_data)

def format_response(response, action, ids):
    if response.status_code != 200:
        return {
            "status": "error",
            "error": response.text,
            "hex": response.content.hex()
        }

    try:
        # Decodifica o JWT para obter informações da conta
        jwt_data = decode_jwt(JWT_TOKEN)
        
        res_pb = wishlist_pb2.CSChangeWishListItemRes()
        res_pb.ParseFromString(response.content)
        
        # Converte a resposta protobuf para dicionário
        pb_dict = MessageToDict(res_pb, preserving_proto_field_name=True)
        
        # Formata os itens da wishlist
        wishlist_items = []
        if 'success_add_item_ids' in pb_dict:
            add_ids = pb_dict['success_add_item_ids']
            # Agrupa em pares (item_id, add_time)
            for i in range(0, len(add_ids), 2):
                if i+1 < len(add_ids):
                    wishlist_items.append({
                        "item_id": add_ids[i],
                        "add_time": add_ids[i+1]
                    })
        
        # Cria a resposta formatada
        formatted_response = {
            "account_id": jwt_data.get('account_id', ''),
            "nickname": jwt_data.get('nickname', ''),
            "region": jwt_data.get('noti_region', ''),
            "status": "success",
            "wishlist_items": wishlist_items
        }
        
        # Adiciona mensagem de ação
        if action == "add":
            formatted_response["response"] = f"Itens {ids} adicionados à wishlist"
        elif action == "del":
            formatted_response["response"] = f"Itens {ids} removidos da wishlist"
        
        return formatted_response
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Erro ao processar resposta: {str(e)}",
            "hex": response.content.hex()
        }

@app.route("/add", methods=["GET"])
def add_items():
    ids = request.args.get("ids")
    if not ids:
        return jsonify({"status": "error", "error": "Parâmetro 'ids' é obrigatório"}), 400

    encrypted_data = build_encrypted_wishlist_data(ids, "")
    response = send_wishlist_request(encrypted_data)
    return jsonify(format_response(response, "add", ids))

@app.route("/del", methods=["GET"])
def del_items():
    ids = request.args.get("ids")
    if not ids:
        return jsonify({"status": "error", "error": "Parâmetro 'ids' é obrigatório"}), 400

    encrypted_data = build_encrypted_wishlist_data("", ids)
    response = send_wishlist_request(encrypted_data)
    return jsonify(format_response(response, "del", ids))

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "routes": {
            "/add?ids=ID1,ID2": "Adiciona itens à wishlist",
            "/del?ids=ID1,ID2": "Remove itens da wishlist"
        },
        "status": "OK"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
