"""Тесты чтения и проверки конфигурационного файла."""

from __future__ import annotations

from pathlib import Path

import pytest

from depvis.config import load_config
from depvis.errors import ConfigError

VALID = """
[package]
name = org.apache.commons:commons-lang3
version = 3.14.0

[repository]
url = https://repo1.maven.org/maven2
test_mode = off
test_file =

[output]
image = graph.png
ascii_tree = on
"""

MAVEN_NAME = "name = org.apache.commons:commons-lang3"
MAVEN_URL = "url = https://repo1.maven.org/maven2"


def to_test_mode(text: str, test_file: str = "") -> str:
    """Перевести конфигурацию в тестовый режим с пакетом A."""
    result = text.replace("test_mode = off", "test_mode = on")
    result = result.replace(MAVEN_NAME, "name = A")
    if test_file:
        result = result.replace("test_file =\n", f"test_file = {test_file}\n")
    return result


@pytest.fixture
def write_config(tmp_path):
    """Фабрика конфигурационных файлов с заданным содержимым."""

    def make(text: str, name: str = "config.ini") -> Path:
        """Записать текст в файл конфигурации и вернуть путь к нему."""
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return make


def test_valid_config_is_parsed(write_config):
    """Корректный файл превращается в объект Config."""
    config = load_config(write_config(VALID))

    assert config.package_name == "org.apache.commons:commons-lang3"
    assert config.package_version == "3.14.0"
    assert config.repository_url == "https://repo1.maven.org/maven2"
    assert config.test_mode is False
    assert config.test_file is None
    assert config.image_path == Path("graph.png")
    assert config.ascii_tree is True


def test_items_cover_all_parameters(write_config):
    """Вывод ключ-значение содержит все параметры."""
    config = load_config(write_config(VALID))

    keys = [key for key, _ in config.as_items()]
    assert keys == [
        "package.name",
        "package.version",
        "repository.url",
        "repository.test_mode",
        "repository.test_file",
        "output.image",
        "output.ascii_tree",
        "output.reverse",
    ]


def test_trailing_slash_in_url_is_removed(write_config):
    """Завершающий слэш в URL отбрасывается."""
    text = VALID.replace("maven2", "maven2/")

    assert load_config(write_config(text)).repository_url.endswith("maven2")


def test_test_mode_requires_existing_file(write_config, tmp_path):
    """В тестовом режиме используется существующий файл репозитория."""
    repo = tmp_path / "repo.txt"
    repo.write_text("A: B\n", encoding="utf-8")

    config = load_config(write_config(to_test_mode(VALID, str(repo))))

    assert config.test_mode is True
    assert config.test_file == repo


def test_missing_file_reports_error(tmp_path):
    """Отсутствующий файл конфигурации — ошибка."""
    with pytest.raises(ConfigError) as info:
        load_config(tmp_path / "no_such.ini")

    assert "не найден" in info.value.message


def test_directory_instead_of_file_reports_error(tmp_path):
    """Каталог вместо файла конфигурации — ошибка."""
    with pytest.raises(ConfigError) as info:
        load_config(tmp_path)

    assert info.value.param == "--config"


def test_broken_ini_reports_error(write_config):
    """Нарушенный формат INI — ошибка."""
    with pytest.raises(ConfigError) as info:
        load_config(write_config("[package\nname = org:artifact\n"))

    assert info.value.param == "--config"


def test_missing_section_reports_error(write_config):
    """Отсутствие обязательной секции — ошибка."""
    text = VALID.split("[output]")[0]

    with pytest.raises(ConfigError) as info:
        load_config(write_config(text))

    assert info.value.param == "output"


@pytest.mark.parametrize(
    ("old", "new", "param"),
    [
        (MAVEN_NAME + "\n", "", "package.name"),
        (MAVEN_NAME, "name = commons lang3", "package.name"),
        ("version = 3.14.0", "version = ../3.14", "package.version"),
        ("version = 3.14.0", "version =", "package.version"),
        (MAVEN_URL, "url = repo1.maven.org", "repository.url"),
        (MAVEN_URL + "\n", "", "repository.url"),
        ("test_mode = off", "test_mode = maybe", "repository.test_mode"),
        ("image = graph.png", "image = graph.jpeg", "output.image"),
        ("image = graph.png", "image = no_dir/graph.png", "output.image"),
        ("ascii_tree = on", "ascii_tree = maybe", "output.ascii_tree"),
        ("ascii_tree = on", "reverse = maybe", "output.reverse"),
        ("[package]", "[package]\nscope = compile", "package.scope"),
        ("[output]", "[extra]\nkey = 1\n\n[output]", "extra"),
    ],
)
def test_invalid_parameter_reports_error(write_config, old, new, param):
    """Ошибка в любом параметре называет этот параметр."""
    with pytest.raises(ConfigError) as info:
        load_config(write_config(VALID.replace(old, new)))

    assert info.value.param == param


def test_parameter_outside_section_reports_error(write_config):
    """Параметр до первой секции — ошибка."""
    with pytest.raises(ConfigError):
        load_config(write_config("[DEFAULT]\nname = x\n" + VALID))


def test_test_mode_rejects_maven_name(write_config):
    """В тестовом режиме имя пакета — большие латинские буквы."""
    text = VALID.replace("test_mode = off", "test_mode = on")

    with pytest.raises(ConfigError) as info:
        load_config(write_config(text))

    assert info.value.param == "package.name"


def test_test_mode_requires_test_file(write_config):
    """В тестовом режиме путь к файлу репозитория обязателен."""
    with pytest.raises(ConfigError) as info:
        load_config(write_config(to_test_mode(VALID)))

    assert info.value.param == "repository.test_file"


def test_test_file_must_exist(write_config, tmp_path):
    """Несуществующий файл тестового репозитория — ошибка."""
    text = to_test_mode(VALID, str(tmp_path / "no_such.txt"))

    with pytest.raises(ConfigError) as info:
        load_config(write_config(text))

    assert "не найден" in info.value.message


def test_test_file_must_not_be_directory(write_config, tmp_path):
    """Каталог вместо файла тестового репозитория — ошибка."""
    with pytest.raises(ConfigError) as info:
        load_config(write_config(to_test_mode(VALID, str(tmp_path))))

    assert info.value.param == "repository.test_file"


def test_image_must_not_be_directory(write_config, tmp_path):
    """Каталог вместо файла изображения — ошибка."""
    folder = tmp_path / "picture.png"
    folder.mkdir()
    text = VALID.replace("image = graph.png", f"image = {folder}")

    with pytest.raises(ConfigError) as info:
        load_config(write_config(text))

    assert info.value.param == "output.image"


@pytest.mark.parametrize("raw", ["on", "yes", "true", "1", "ДА"])
def test_boolean_synonyms_are_accepted(write_config, raw):
    """Положительные логические значения принимаются."""
    text = VALID.replace("ascii_tree = on", f"ascii_tree = {raw}")

    assert load_config(write_config(text)).ascii_tree is True


@pytest.mark.parametrize("raw", ["off", "no", "false", "0", "НЕТ"])
def test_boolean_negative_synonyms_are_accepted(write_config, raw):
    """Отрицательные логические значения принимаются."""
    text = VALID.replace("ascii_tree = on", f"ascii_tree = {raw}")

    assert load_config(write_config(text)).ascii_tree is False


def test_empty_boolean_means_default(write_config):
    """Пустое логическое значение означает значение по умолчанию."""
    text = VALID.replace("ascii_tree = on", "ascii_tree =")

    assert load_config(write_config(text)).ascii_tree is False


def test_reverse_mode_is_off_by_default(write_config):
    """Режим обратных зависимостей по умолчанию выключен."""
    assert load_config(write_config(VALID)).reverse is False


def test_reverse_mode_can_be_enabled(write_config):
    """Режим обратных зависимостей включается параметром reverse."""
    text = VALID + "reverse = on\n"

    assert load_config(write_config(text)).reverse is True
