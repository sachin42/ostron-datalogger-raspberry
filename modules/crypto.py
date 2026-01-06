import base64

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad

from .utils import get_signature_timestamp


def encrypt_payload(plain_json: str, token_id: str) -> str:
    """Encrypt payload using AES"""
    key = SHA256.new(token_id.encode()).digest()
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(plain_json.encode(), 16))
    return base64.b64encode(encrypted).decode()


def generate_signature(token_id: str, public_key_pem: str) -> str:
    """Generate RSA signature"""
    message = f"{token_id}$*{get_signature_timestamp()}".encode()
    pub_key = RSA.import_key(public_key_pem)
    cipher = PKCS1_OAEP.new(pub_key, hashAlgo=SHA256)
    encrypted = cipher.encrypt(message)
    return base64.b64encode(encrypted).decode()
