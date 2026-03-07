import json
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from django.conf import settings


class SecretCryptoService:

    def __init__(self):
        self.fernet = MultiFernet([Fernet(k) for k in settings.SECRET_FIELD_KEYS])

    def encrypt_text(self, value: str):
        if value is None:
            return None
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt_text(self, value: str):
        if value is None:
            return None
        return self.fernet.decrypt(value.encode()).decode()

    def encrypt_json(self, value):
        if value is None:
            return None
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        return self.encrypt_text(raw)

    def decrypt_json(self, value):
        if value is None:
            return None
        raw = self.decrypt_text(value)
        return json.loads(raw)


secret_crypto = SecretCryptoService()