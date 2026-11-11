"""Тесты точки входа приложения."""

from __future__ import annotations

from pathlib import Path

import pytest

import main

ROOT = Path(__file__).resolve().parents[1]

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

PARAMETERS = [
    "package.name",
    "package.version",
    "repository.url",
    "repository.test_mode",
    "repository.test_file",
    "output.image",
    "output.ascii_tree",
]


def test_default_config_is_printed(capsys):
    """Все параметры конфигурации выводятся в виде ключ-значение."""
    code = main.main(["--config", str(ROOT / "config.ini")])

    out = capsys.readouterr().out
    assert code == 0
    assert "org.apache.commons:commons-lang3" in out
    for key in PARAMETERS:
        assert f"  {key}" in out


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
