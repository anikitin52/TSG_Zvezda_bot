from enum import Enum


class UserRole(Enum):
    ADMIN = 'admin'
    MANAGER = 'manager'
    ACCOUNTANT = 'accountant'
    PLUMBER = 'plumber'
    ELECTRIC = 'electric'
    CITIZEN = 'citizen'

    @classmethod
    def from_string(cls, value):
        """
        Конвертирует строку в UserRole
        Returns:
            UserRole enum или None если строка невалидна
        """
        if value is None:
            return None
        try:
            return cls(value)
        except ValueError:
            return None


class ResponseStatus(Enum):
    OK = 'ok'
    ERROR = 'error'
