"""Тесты координат пакета."""

from __future__ import annotations

import pytest

from depvis.package import Package, PackageError


def test_maven_name_and_version_are_parsed():
    """Координаты Maven и версия разбираются по частям."""
    package = Package.parse("org.example:app", "1.0")

    assert package.group == "org.example"
    assert package.artifact == "app"
    assert package.name == "org.example:app"
    assert package.coordinates == "org.example:app:1.0"


def test_version_inside_name_is_parsed():
    """Версия может быть указана третьей частью координат."""
    assert Package.parse("org.example:app:2.0").version == "2.0"


def test_test_package_has_no_group():
    """Пакет тестового репозитория хранится без groupId."""
    package = Package.parse("A")

    assert package.group == ""
    assert package.name == "A"
    assert str(package) == "A"


@pytest.mark.parametrize(
    "text", ["", "   ", "a", "org.example:", ":app", "a:b:c:d"]
)
def test_invalid_name_reports_error(text):
    """Некорректные координаты — ошибка."""
    with pytest.raises(PackageError):
        Package.parse(text)


def test_with_version_returns_new_package():
    """Смена версии создаёт новый пакет и не меняет исходный."""
    package = Package.parse("org.example:app", "1.0")

    assert package.with_version("2.0").coordinates == "org.example:app:2.0"
    assert package.version == "1.0"
