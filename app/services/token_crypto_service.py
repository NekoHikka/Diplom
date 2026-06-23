import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import Config


class TokenCryptoService:
    PREFIX = "enc:v1:"

    @staticmethod
    def _secret():
        secret = Config.MONOBANK_TOKEN_SECRET
        if not secret or secret == "fallback-secret-key":
            raise RuntimeError("MONOBANK_TOKEN_SECRET or SECRET_KEY must be configured")
        return secret

    @staticmethod
    def _fernet():
        digest = hashlib.sha256(TokenCryptoService._secret().encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)

    @staticmethod
    def is_encrypted(value):
        return bool(value and value.startswith(TokenCryptoService.PREFIX))

    @staticmethod
    def encrypt(value):
        if not value:
            return value
        if TokenCryptoService.is_encrypted(value):
            return value
        token = TokenCryptoService._fernet().encrypt(value.encode("utf-8")).decode("utf-8")
        return f"{TokenCryptoService.PREFIX}{token}"

    @staticmethod
    def decrypt(value):
        if not value:
            return value
        if not TokenCryptoService.is_encrypted(value):
            return value
        encrypted_value = value[len(TokenCryptoService.PREFIX):]
        try:
            return TokenCryptoService._fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Stored Monobank token cannot be decrypted") from exc
