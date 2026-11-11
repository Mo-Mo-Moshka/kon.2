"""Тесты точки входа приложения."""

from __future__ import annotations

from pathlib import Path

import pytest

import main
from depvis.maven import RepositoryError
from depvis.package import Package

ROOT = Path(__file__).resolve().parents[1]

MAVEN_CONFIG = """
[package]
name = org.example:app
version = 1.0

[repository]
url = https://repo.example.org/maven2
test_mode = off
test_file =

[output]
image = {image}
ascii_tree = on
"""

TEST_CONFIG = """
[package]
name = {name}
version = 1.0

[repository]
url =
test_mode = on
test_file = {repo}

[output]
image = {image}
ascii_tree = {tree}
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
        """Зависимости корня или ошибка, заданная в тесте."""
        if self.error:
            raise RepositoryError(self.error)
        if package.artifact == "app":
            return list(self.answer)
        return []


@pytest.fixture
def maven_config(tmp_path, monkeypatch):
    """Конфигурация Maven с подменённым репозиторием."""
    monkeypatch.setattr(main, "MavenRepository", FakeRepository)
    FakeRepository.answer = []
    FakeRepository.error = ""
    path = tmp_path / "config.ini"
    image = (tmp_path / "graph.png").as_posix()
    path.write_text(MAVEN_CONFIG.format(image=image), encoding="utf-8")
    return str(path)


@pytest.fixture
def repo_config(tmp_path):
    """Фабрика конфигураций тестового репозитория."""

    def make(repo_text: str, name: str = "A", tree: str = "on") -> str:
        """Записать репозиторий и конфигурацию, вернуть путь к ней."""
        repo = tmp_path / "repo.txt"
        repo.write_text(repo_text, encoding="utf-8")
        path = tmp_path / "config.ini"
        text = TEST_CONFIG.format(
            name=name,
            repo=repo.as_posix(),
            image=(tmp_path / "graph.png").as_posix(),
            tree=tree,
        )
        path.write_text(text, encoding="utf-8")
        return str(path)

    return make


def test_maven_graph_is_printed(capsys, maven_config):
    """Граф пакета Maven выводится вместе с зависимостями."""
    FakeRepository.answer = [Package("org.example", "core", "2.0")]

    code = main.main(["--config", maven_config])

    out = capsys.readouterr().out
    assert code == 0
    assert "org.example:app:1.0 -> org.example:core:2.0" in out
    assert "org.example:core:2.0 -> зависимостей нет" in out


def test_repository_error_is_reported(capsys, maven_config):
    """Ошибка репозитория выводится, код возврата 1."""
    FakeRepository.error = "HTTP 404 Not Found"

    code = main.main(["--config", maven_config])

    assert code == 1
    assert "404" in capsys.readouterr().err


def test_graph_of_test_repository_is_printed(capsys, repo_config):
    """Граф тестового репозитория выводится вместе с циклами."""
    code = main.main(["--config", repo_config("A: B C\nB: D\nC: D\nD: A\n")])

    out = capsys.readouterr().out
    assert code == 0
    assert "пакетов: 4" in out
    assert "A -> B, C" in out
    assert "A -> B -> D -> A" in out


def test_unresolved_package_is_listed(capsys, repo_config):
    """Неописанный пакет перечисляется отдельно."""
    code = main.main(["--config", repo_config("A: B\n")])

    assert code == 0
    assert "Не удалось получить зависимости:" in capsys.readouterr().out


def test_unknown_root_in_test_repository_reports_error(capsys, repo_config):
    """Корневого пакета нет в тестовом репозитории — ошибка."""
    code = main.main(["--config", repo_config("A: B\nB:\n", name="Z")])

    assert code == 1
    assert "не описан" in capsys.readouterr().err


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
