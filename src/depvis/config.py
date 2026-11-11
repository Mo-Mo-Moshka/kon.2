"""Чтение и проверка конфигурационного файла формата INI.

Единственным источником настраиваемых пользователем параметров
является INI-файл. Модуль превращает его в объект :class:`Config`
и подробно сообщает обо всех ошибках заполнения.

Регулярные выражения модуля:

- ``MAVEN_NAME_RE`` — координаты Maven вида ``groupId:artifactId``;
- ``TEST_NAME_RE`` — имя пакета тестового репозитория (большие
  латинские буквы);
- ``VERSION_RE`` — версия пакета (``1.0``, ``3.14.0-RC1`` и т. п.).
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

SCHEMA: dict[str, tuple[str, ...]] = {
    "package": ("name", "version"),
    "repository": ("url", "test_mode", "test_file"),
    "output": ("image", "ascii_tree"),
}

TRUE_VALUES = frozenset({"1", "true", "yes", "on", "да"})
FALSE_VALUES = frozenset({"0", "false", "no", "off", "нет"})

MAVEN_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+$")
TEST_NAME_RE = re.compile(r"^[A-Z]+$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-+]*$")
URL_RE = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)

NOT_SET = "<не задан>"


@dataclass(frozen=True)
class Config:
    """Набор настраиваемых пользователем параметров."""

    package_name: str
    package_version: str
    repository_url: str
    test_mode: bool
    test_file: Path | None
    image_path: Path
    ascii_tree: bool

    def as_items(self) -> list[tuple[str, str]]:
        """Параметры в виде пар ключ-значение для вывода на экран."""
        test_file = str(self.test_file) if self.test_file else NOT_SET
        return [
            ("package.name", self.package_name),
            ("package.version", self.package_version),
            ("repository.url", self.repository_url or NOT_SET),
            ("repository.test_mode", format_bool(self.test_mode)),
            ("repository.test_file", test_file),
            ("output.image", str(self.image_path)),
            ("output.ascii_tree", format_bool(self.ascii_tree)),
        ]


def format_bool(value: bool) -> str:
    """Логическое значение в том же виде, в каком оно пишется в INI."""
    return "on" if value else "off"


def load_config(path: str | Path) -> Config:
    """Прочитать конфигурационный файл и проверить все параметры.

    :raises ConfigError: файл не найден, повреждён или параметр
        задан неверно.
    """
    parser = read_ini(Path(path))
    check_schema(parser)

    test_mode = get_bool(parser, "repository", "test_mode", default=False)
    name = get_required(parser, "package", "name")
    check_name(name, test_mode)
    version = get_required(parser, "package", "version")
    check_version(version)

    url, test_path = check_source(
        get_optional(parser, "repository", "url"),
        get_optional(parser, "repository", "test_file"),
        test_mode,
    )

    return Config(
        package_name=name,
        package_version=version,
        repository_url=url,
        test_mode=test_mode,
        test_file=test_path,
        image_path=check_image(get_required(parser, "output", "image")),
        ascii_tree=get_bool(parser, "output", "ascii_tree", default=False),
    )


def read_ini(path: Path) -> configparser.ConfigParser:
    """Прочитать INI-файл, сообщив о проблемах с самим файлом."""
    if not path.exists():
        raise ConfigError("--config", f"файл конфигурации не найден: {path}")
    if path.is_dir():
        raise ConfigError("--config", f"ожидался файл, а не каталог: {path}")

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with path.open(encoding="utf-8") as handle:
            parser.read_file(handle)
    except UnicodeDecodeError as exc:
        raise ConfigError(
            "--config", f"файл должен быть в кодировке UTF-8 ({exc.reason})"
        ) from exc
    except configparser.Error as exc:
        raise ConfigError(
            "--config", f"некорректный формат INI: {exc}"
        ) from exc
    return parser


def check_schema(parser: configparser.ConfigParser) -> None:
    """Проверить, что в файле нет лишних секций и ключей."""
    if parser.defaults():
        unknown = ", ".join(sorted(parser.defaults()))
        raise ConfigError(
            "", f"параметры вне секции не поддерживаются: {unknown}"
        )

    for section in parser.sections():
        if section not in SCHEMA:
            known = ", ".join(SCHEMA)
            raise ConfigError(
                section, f"неизвестная секция, допустимы только: {known}"
            )
        check_keys(parser, section)

    for section in SCHEMA:
        if not parser.has_section(section):
            raise ConfigError(section, "отсутствует обязательная секция")


def check_keys(parser: configparser.ConfigParser, section: str) -> None:
    """Проверить, что в секции нет неизвестных параметров."""
    for key in parser[section]:
        if key not in SCHEMA[section]:
            known = ", ".join(SCHEMA[section])
            raise ConfigError(
                f"{section}.{key}",
                f"неизвестный параметр, допустимы только: {known}",
            )


def get_optional(
    parser: configparser.ConfigParser, section: str, key: str
) -> str:
    """Значение необязательного параметра или пустая строка."""
    return parser.get(section, key, fallback="").strip()


def get_required(
    parser: configparser.ConfigParser, section: str, key: str
) -> str:
    """Значение обязательного параметра."""
    if not parser.has_option(section, key):
        raise ConfigError(f"{section}.{key}", "обязательный параметр не задан")
    value = parser.get(section, key).strip()
    if not value:
        raise ConfigError(f"{section}.{key}", "значение не может быть пустым")
    return value


def get_bool(
    parser: configparser.ConfigParser,
    section: str,
    key: str,
    *,
    default: bool,
) -> bool:
    """Логический параметр, записанный как on/off, yes/no, true/false."""
    raw = get_optional(parser, section, key).lower()
    if not raw:
        return default
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    allowed = ", ".join(sorted(TRUE_VALUES | FALSE_VALUES))
    raise ConfigError(
        f"{section}.{key}",
        f"ожидалось логическое значение ({allowed}), получено {raw!r}",
    )


def check_name(name: str, test_mode: bool) -> None:
    """Проверить имя анализируемого пакета."""
    if test_mode:
        if not TEST_NAME_RE.match(name):
            raise ConfigError(
                "package.name",
                "в тестовом режиме имя пакета состоит из больших "
                f"латинских букв, получено {name!r}",
            )
        return
    if not MAVEN_NAME_RE.match(name):
        raise ConfigError(
            "package.name",
            "ожидались координаты Maven вида groupId:artifactId, "
            f"получено {name!r}",
        )


def check_version(version: str) -> None:
    """Проверить версию пакета."""
    if not VERSION_RE.match(version):
        raise ConfigError(
            "package.version", f"недопустимая версия пакета: {version!r}"
        )


def check_source(
    url: str, test_file: str, test_mode: bool
) -> tuple[str, Path | None]:
    """Проверить источник данных: URL репозитория или тестовый файл."""
    if test_mode:
        return url, check_test_file(test_file)
    if not url:
        raise ConfigError(
            "repository.url",
            "нужно указать URL репозитория или включить тестовый режим",
        )
    if not URL_RE.match(url):
        raise ConfigError(
            "repository.url",
            f"ожидался адрес вида http(s)://host/path, получено {url!r}",
        )
    return url.rstrip("/"), None


def check_test_file(test_file: str) -> Path:
    """Проверить путь к файлу описания тестового репозитория."""
    if not test_file:
        raise ConfigError(
            "repository.test_file",
            "в тестовом режиме нужно указать путь к файлу описания графа",
        )
    path = Path(test_file)
    if not path.exists():
        raise ConfigError("repository.test_file", f"файл не найден: {path}")
    if not path.is_file():
        raise ConfigError(
            "repository.test_file", f"ожидался файл, а не каталог: {path}"
        )
    return path


def check_image(value: str) -> Path:
    """Проверить имя файла с изображением графа."""
    path = Path(value)
    if path.suffix.lower() != ".png":
        raise ConfigError(
            "output.image",
            "изображение графа сохраняется в формате PNG, "
            f"получено {value!r}",
        )
    if path.is_dir():
        raise ConfigError(
            "output.image", f"ожидался файл, а не каталог: {path}"
        )
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.exists():
        raise ConfigError(
            "output.image",
            f"каталог для изображения не существует: {parent}",
        )
    return path
