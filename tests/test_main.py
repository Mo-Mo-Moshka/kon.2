"""Тесты точки входа приложения."""

from __future__ import annotations

from pathlib import Path

import pytest

import main
from depvis.maven import RepositoryError
from depvis.package import Package

ROOT = Path(__file__).resolve().parents[1]

CONFIG = """
[package]
name = org.example:app
version = 1.0

[repository]
url = https://repo.example.org/maven2
test_mode = off
test_file =

[output]
image = graph.png
ascii_tree = on
"""

EXAMPLE_ERRORS = [
    "bad_missing_name.ini",
    "bad_name.ini",
    "bad_version.ini",
    "bad_url.ini",
    "bad_test_mode.ini",
    "bad_test_file.ini",
    "bad_image.ini",
    "bad_ascii_tree.ini",
    "bad_syntax.ini",
    "bad_unknown_key.ini",
]


class FakeRepository:
    """Репозиторий Maven с заранее известными зависимостями."""

    answer: list[Package] = []
    error: str = ""

    def __init__(self, url: str) -> None:
        """Запомнить адрес репозитория."""
        self.url = url

    def dependencies(self, package: Package) -> list[Package]:
        """Заданные в тесте зависимости или ошибка."""
        if self.error:
            raise RepositoryError(self.error)
        return list(self.answer)


@pytest.fixture
def maven_config(tmp_path, monkeypatch):
    """Конфигурация Maven с подменённым репозиторием."""
    monkeypatch.setattr(main, "MavenRepository", FakeRepository)
    FakeRepository.answer = []
    FakeRepository.error = ""
    path = tmp_path / "config.ini"
    path.write_text(CONFIG, encoding="utf-8")
    return str(path)


def test_direct_dependencies_are_printed(capsys, maven_config):
    """Прямые зависимости пакета выводятся списком."""
    FakeRepository.answer = [
        Package("org.example", "core", "2.0"),
        Package("org.example", "log", "1.5"),
    ]

    code = main.main(["--config", maven_config])

    out = capsys.readouterr().out
    assert code == 0
    assert "Прямые зависимости пакета org.example:app:1.0:" in out
    assert "  org.example:core:2.0" in out
    assert "  org.example:log:1.5" in out


def test_package_without_dependencies(capsys, maven_config):
    """Пакет без зависимостей отмечается явно."""
    code = main.main(["--config", maven_config])

    assert code == 0
    assert "зависимостей нет" in capsys.readouterr().out


def test_repository_error_is_reported(capsys, maven_config):
    """Ошибка репозитория выводится, код возврата 1."""
    FakeRepository.error = "HTTP 404 Not Found"

    code = main.main(["--config", maven_config])

    assert code == 1
    assert "404" in capsys.readouterr().err


def test_test_mode_is_not_supported_yet(capsys):
    """Тестовый репозиторий на этом этапе ещё не поддерживается."""
    code = main.main(["--config", str(ROOT / "examples" / "test_mode.ini")])

    assert code == 1
    assert "следующем этапе" in capsys.readouterr().err


def test_invalid_config_reports_error_and_exit_code(capsys, tmp_path):
    """Ошибка конфигурации выводится в stderr, код возврата 1."""
    bad = tmp_path / "bad.ini"
    bad.write_text("[package]\nname = A\n", encoding="utf-8")

    code = main.main(["--config", str(bad)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "Ошибка конфигурации" in captured.err


@pytest.mark.parametrize("name", EXAMPLE_ERRORS)
def test_example_errors_are_reported(capsys, name):
    """Каждый пример ошибочной конфигурации отвергается."""
    code = main.main(["--config", str(ROOT / "examples" / name)])

    assert code == 1
    assert "Ошибка конфигурации" in capsys.readouterr().err
