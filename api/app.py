from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import random
import requests
import jwt

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse URL and query parameters
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        
        item_id = query.get('id', [None])[0]
        
        if not item_id:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "message": "ID do item não fornecido"
            }).encode())
            return

        # 1. Get random credentials
        try:
            with open('api/credentials.txt', 'r') as f:
                lines = f.readlines()
                line = random.choice(lines).strip()
                uid, password = line.split(':', 1)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "message": f"Erro ao ler credenciais: {str(e)}"
            }).encode())
            return

        # 2. Get JWT token
        try:
            jwt_url = f"https://genjwt.vercel.app/api/get_jwt?type=4&guest_uid={uid}&guest_password={password}"
            jwt_response = requests.get(jwt_url)
            jwt_data = jwt_response.json()
            
            if not jwt_data.get('success'):
                raise Exception(jwt_data)
                
            token = jwt_data['BearerAuth']
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "message": f"Erro ao obter JWT: {str(e)}"
            }).encode())
            return

        # 3. Add to wishlist
        try:
            wishlist_url = f"https://dev-wishlist-add.vercel.app/add-wishlist?itemId={item_id}&region=BR&token={token}"
            wishlist_response = requests.get(wishlist_url)
            wishlist_data = wishlist_response.json()
            
            if not wishlist_data.get('success'):
                raise Exception(wishlist_data)
                
            # 4. Decode token
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "wishlist_response": wishlist_data,
                "account_info": {
                    "uid": decoded.get('external_uid'),
                    "account_id": decoded.get('account_id'),
                    "nickname": decoded.get('nickname')
                },
                "jwt_response": jwt_data
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "message": f"Erro na wishlist: {str(e)}"
            }).encode())
