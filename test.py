import json
import base64
import requests
import pytz
from datetime import datetime

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad

# ==================== USER CONFIG ===============================

CPCB_ENDPOINT = "https://cems.cpcb.gov.in/v1.0/industry/data"

DEVICE_ID  = "device_7025"
TOKEN_ID   = "Hvg_LrxeePXexh7TM76jQqWsWGRV4M4gvX1_tvKDMN4="
STATION_ID = "station_8203"

CPCB_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1O3KxMEcKajtHHAW+IlQ
7aHFTZGeC3nHq/ZomJtcmBQ9+hd4Epq7fiEQhsDpItFu3y1TmXtozHNqXFxRqllK
Zw8e9li3RrbGRZBFrKy1wQ70XUr3uv0w4TV0cHgvAlnLXdAkaGDyYDf+fVsqIYJD
GFOIzGYCdzY5vMNpEidIIEqKsCUyJqAc/wf2eIwKm4bhca+YW670532p4RGYapyR
3Hjs90hAH+8I4V8Oklw8NEtkX+acSlcKd+FQcUA14IWBrX+fB6bhkA2jyzsfVXVr
VVxLYJ89LBETrXSd5eKLTgdNJNSiSrIqjSNCgxsNGuauccYZnef/QmVD2/YI60kE
pwIDAQAB
-----END PUBLIC KEY-----"""

# ==================== TIME UTILITIES ============================

IST = pytz.timezone("Asia/Kolkata")


def get_aligned_timestamp_ms():
    """Return epoch ms aligned to 00/15/30/45 IST"""
    now = datetime.now(IST)
    aligned_minute = (now.minute // 15) * 15
    aligned = now.replace(minute=aligned_minute, second=0, microsecond=0)
    return int(aligned.timestamp() * 1000)


def get_signature_timestamp():
    """Timestamp format required for CPCB signature"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

# ==================== PAYLOAD BUILD =============================


def build_plain_payload(value):
    payload = {
        "data": [
            {
                "stationId": STATION_ID,
                "device_data": [
                    {
                        "deviceId": DEVICE_ID,
                        "params": [
                            {
                                "parameter": "ph",
                                "value": value,
                                "unit": "pH",
                                "timestamp": get_aligned_timestamp_ms(),
                                "flag": "U"
                            }
                        ]
                    }
                ],
                "latitude": 28.6129,
                "longitude": 77.2295
            }
        ]
    }

    return json.dumps(payload, separators=(",", ":"))

# ==================== AES ENCRYPTION ============================


def encrypt_payload(plain_json: str) -> str:
    """AES-256 ECB encryption with SHA256(Token) key"""
    key = SHA256.new(TOKEN_ID.encode()).digest()
    cipher = AES.new(key, AES.MODE_ECB)

    encrypted = cipher.encrypt(pad(plain_json.encode(), 16))
    return base64.b64encode(encrypted).decode()

# ==================== RSA SIGNATURE =============================


def generate_signature() -> str:
    message = f"{TOKEN_ID}$*{get_signature_timestamp()}".encode()

    pub_key = RSA.import_key(CPCB_PUBLIC_KEY_PEM)
    cipher = PKCS1_OAEP.new(pub_key, hashAlgo=SHA256)

    encrypted = cipher.encrypt(message)
    return base64.b64encode(encrypted).decode()

# ==================== HTTP SEND ================================


def send_to_cpcb(value: float):
    plain_json = build_plain_payload(value)
    encrypted_payload = encrypt_payload(plain_json)
    signature = generate_signature()

    headers = {
        "Content-Type": "text/plain",
        "X-Device-Id": DEVICE_ID,
        "signature": signature
    }

    print("\n===== PLAIN JSON =====")
    print(plain_json)

    print("\n===== ENCRYPTED PAYLOAD =====")
    print(encrypted_payload)

    print("\n===== HEADERS =====")
    for k, v in headers.items():
        print(f"{k}: {v}")

    response = requests.post(
        CPCB_ENDPOINT,
        data=encrypted_payload,
        headers=headers,
        timeout=20
    )

    print("\n===== CPCB RESPONSE =====")
    print("HTTP Status:", response.status_code)
    print("Body:", response.text)

# ==================== MAIN =====================================

if __name__ == "__main__":
    # Example value to send (pH)
    send_to_cpcb(8.20)
