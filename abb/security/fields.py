from django.db import models
from .crypto import secret_crypto



class EncryptedTextField(models.TextField):
    description = "Encrypted text field"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return secret_crypto.decrypt_text(value)

    def to_python(self, value):
        # When already loaded into python, keep as-is.
        if value is None or not isinstance(value, str):
            return value
        return value

    def get_prep_value(self, value):
        if value is None:
            return value
        return secret_crypto.encrypt_text(str(value))


class EncryptedJSONField(models.TextField):

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return secret_crypto.decrypt_json(value)

    def to_python(self, value):
        if isinstance(value, (dict, list)) or value is None:
            return value
        return value

    def get_prep_value(self, value):
        if value is None:
            return value
        return secret_crypto.encrypt_json(value)