from flask import Flask, request, jsonify
import base64
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Util.Padding import unpad
import json

app = Flask(__name__)

# Test credentials
TOKEN_ID = "Hvg_LrxeePXexh7TM76jQqWsWGRV4M4gvX1_tvKDMN4="
DEVICE_ID = "device_7025"
STATION_ID = "station_8203"
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1O3KxMEcKajtHHAW+IlQ
7aHFTZGeC3nHq/ZomJtcmBQ9+hd4Epq7fiEQhsDpItFu3y1TmXtozHNqXFxRqllK
Zw8e9li3RrbGRZBFrKy1wQ70XUr3uv0w4TV0cHgvAlnLXdAkaGDyYDf+fVsqIYJD
GFOIzGYCdzY5vMNpEidIIEqKsCUyJqAc/wf2eIwKm4bhca+YW670532p4RGYapyR
3Hjs90hAH+8I4V8Oklw8NEtkX+acSlcKd+FQcUA14IWBrX+fB6bhkA2jyzsfVXVr
VVxLYJ89LBETrXSd5eKLTgdNJNSiSrIqjSNCgxsNGuauccYZnef/QmVD2/YI60kE
pwIDAQAB
-----END PUBLIC KEY-----"""

def decrypt_payload(encrypted_b64, token_id):
    key = SHA256.new(token_id.encode()).digest()
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = base64.b64decode(encrypted_b64)
    decrypted = unpad(cipher.decrypt(encrypted), 16)
    return decrypted.decode()

# For testing, skip signature verification

@app.route('/v1.0/industry/data', methods=['POST'])
def receive_data():
    try:
        encrypted_payload = request.data.decode()
        device_id = request.headers.get('X-Device-Id')
        signature = request.headers.get('signature')

        print(f"Received data from device: {device_id}")
        print(f"Encrypted payload length: {len(encrypted_payload)}")
        print(f"Signature: {signature}")

        # Attempt to decrypt
        try:
            plain_json = decrypt_payload(encrypted_payload, TOKEN_ID)
            data = json.loads(plain_json)
            print(f"Decrypted data: {json.dumps(data, indent=2)}")
        except Exception as decrypt_error:
            print(f"Decryption failed: {decrypt_error}")
            print(f"Raw encrypted: {encrypted_payload[:100]}...")
            data = {"error": "decryption_failed"}

        # For testing, always return success
        response = {"msg":"success","status": 1}
        return response, 200

    except Exception as e:
        print(f"Error processing request: {e}")
        return {"msg": "error", "status": 0}, 400
if __name__ == '__main__':
    print("Starting test server on http://localhost:5000")
    print("Use this as endpoint: http://localhost:5000/v1.0/industry/data")
    app.run(host='0.0.0.0', port=5000, debug=True)