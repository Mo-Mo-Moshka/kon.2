"""Ошибки приложения."""


class DepVisError(Exception):
    """Базовая ошибка инструмента визуализации зависимостей."""


class ConfigError(DepVisError):
    """Ошибка чтения или проверки конфигурационного файла.

    Хранит путь к параметру (``секция.ключ``) и понятное описание
    проблемы, чтобы пользователь сразу видел, что именно исправить.
    """

    def __init__(self, param: str, message: str) -> None:
        """Запомнить параметр и описание ошибки."""
        self.param = param
        self.message = message
        super().__init__(f"{param}: {message}" if param else message)
