from cryptography.fernet import Fernet


class EncryptionService:
    def __init__(self, key: str):
        self._fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()
