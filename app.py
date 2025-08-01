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
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInN2ciI6IjIiLCJ0eXAiOiJKV1QifQ.eyJhY2NvdW50X2lkIjoxMTA2MjkxMDY1Nywibmlja25hbWUiOiJUSFVHX2RLNGJPdGgiLCJub3RpX3JlZ2lvbiI6IkJSIiwibG9ja19yZWdpb24iOiJCUiIsImV4dGVybmFsX2lkIjoiZWZjNDFkZjMwMmZlYzc1ZmM2ZjIxNTUzYzMwNjE4NTEiLCJleHRlcm5hbF90eXBlIjo0LCJwbGF0X2lkIjoxLCJjbGllbnRfdmVyc2lvbiI6IjEuMTExLjEiLCJlbXVsYXRvcl9zY29yZSI6MTAwLCJpc19lbXVsYXRvciI6dHJ1ZSwiY291bnRyeV9jb2RlIjoiVVMiLCJleHRlcm5hbF91aWQiOjM3NDMzMjcwNTQsInJlZ19hdmF0YXIiOjEwMjAwMDAwNywic291cmNlIjowLCJsb2NrX3JlZ2lvbl90aW1lIjoxNzM4OTcyOTY0LCJjbGllbnRfdHlwZSI6Miwic2lnbmF0dXJlX21kNSI6IiIsInVzaW5nX3ZlcnNpb24iOjAsInJlbGVhc2VfY2hhbm5lbCI6IiIsInJlbGVhc2VfdmVyc2lvbiI6Ik9CNTAiLCJleHAiOjE3NTM5OTk4MDR9._ZWRS6Ntpg_VJcl_DSXqwlWx5wOT8HLGtx6Lp4MwUwI"

def decode_jwt(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return {
            "account_id": decoded.get("account_id"),
            "nickname": decoded.get("nickname"),
            "region": decoded.get("noti_region", decoded.get("lock_region", "UNKNOWN")),
            "external_id": decoded.get("external_id")
        }
    except Exception as e:
        return {
            "error": f"Erro ao decodificar JWT: {str(e)}"
        }

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
        res_pb = wishlist_pb2.CSChangeWishListItemRes()
        res_pb.ParseFromString(response.content)
        
        # Decodificar JWT para obter informações do usuário
        user_info = decode_jwt(JWT_TOKEN)
        
        # Processar wishlist items
        wishlist_items = []
        if action == "add":
            success_ids = res_pb.success_add_item_ids
            # O formato é [8, item_id, 16, timestamp, ...]
            for i in range(1, len(success_ids), 4):
                if i+1 < len(success_ids):
                    item_id = success_ids[i]
                    timestamp = success_ids[i+2] if i+2 < len(success_ids) else int(datetime.now().timestamp())
                    wishlist_items.append({
                        "item_id": item_id,
                        "add_time": timestamp
                    })
            
            response_message = f"Items {ids} added to wishlist" if len(wishlist_items) > 1 else f"Item {ids} added to wishlist"
        else:
            success_ids = res_pb.success_del_item_ids
            response_message = f"Items {ids} removed from wishlist" if len(success_ids) > 1 else f"Item {ids} removed from wishlist"

        return {
            "account_id": user_info.get("account_id"),
            "nickname": user_info.get("nickname"),
            "region": user_info.get("region"),
            "response": response_message,
            "status": "success",
            "wishlist_items": wishlist_items
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": "Erro ao decodificar resposta Protobuf",
            "exception": str(e),
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
    user_info = decode_jwt(JWT_TOKEN)
    return jsonify({
        "account_info": {
            "account_id": user_info.get("account_id"),
            "nickname": user_info.get("nickname"),
            "region": user_info.get("region")
        },
        "routes": {
            "/add?ids=ID1,ID2": "Adiciona itens à wishlist",
            "/del?ids=ID1,ID2": "Remove itens da wishlist"
        },
        "status": "OK"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
