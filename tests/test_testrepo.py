"""Тесты файла описания тестового репозитория."""

from __future__ import annotations

from pathlib import Path

import pytest

from depvis.package import Package
from depvis.testrepo import TestRepository, TestRepositoryError

ROOT = Path(__file__).resolve().parents[1]


def parse(text: str) -> TestRepository:
    """Разобрать описание тестового репозитория."""
    return TestRepository.parse(text, "repo.txt")


def names(packages) -> list[str]:
    """Имена пакетов списком строк."""
    return [package.name for package in packages]


def dependencies_of(text: str, name: str) -> list[str]:
    """Имена прямых зависимостей пакета из описания репозитория."""
    return names(parse(text).dependencies(Package("", name)))


def test_packages_and_dependencies_are_read():
    """Пакеты и их зависимости читаются из описания."""
    repo = parse("A: B C\nB: D\nC:\nD:\n")

    assert names(repo.packages()) == ["A", "B", "C", "D"]
    assert names(repo.dependencies(Package("", "A"))) == ["B", "C"]
    assert repo.dependencies(Package("", "C")) == []


def test_comments_and_blank_lines_are_skipped():
    """Комментарии и пустые строки пропускаются."""
    repo = parse("# комментарий\n\n; ещё комментарий\nA: B\nB:\n")

    assert names(repo.packages()) == ["A", "B"]


def test_commas_are_allowed_as_separators():
    """Зависимости можно разделять запятыми."""
    assert dependencies_of("A: B, C\nB:\nC:\n", "A") == ["B", "C"]


def test_duplicate_dependency_is_taken_once():
    """Повторённая зависимость учитывается один раз."""
    assert dependencies_of("A: B B\nB:\n", "A") == ["B"]


def test_undeclared_package_is_still_listed():
    """Пакет, упомянутый только как зависимость, тоже известен."""
    repo = parse("A: B\n")

    assert names(repo.packages()) == ["A", "B"]
    assert repo.has(Package("", "A")) is True
    assert repo.has(Package("", "B")) is False


def test_undeclared_package_has_no_dependencies():
    """Зависимости неописанного пакета получить нельзя."""
    with pytest.raises(TestRepositoryError) as info:
        dependencies_of("A: B\n", "B")

    assert "не описан" in str(info.value)


@pytest.mark.parametrize(
    "text",
    [
        "A B C\n",
        "a: B\n",
        "A1: B\n",
        "A: b\n",
        "A: B\nA: C\n",
        "",
        "# только комментарий\n",
    ],
)
def test_broken_description_reports_error(text):
    """Ошибки в описании репозитория обнаруживаются."""
    with pytest.raises(TestRepositoryError):
        parse(text)


def test_file_is_read_from_disk():
    """Описание читается из файла на диске."""
    repo = TestRepository.load(ROOT / "examples" / "repo_tree.txt")

    assert names(repo.dependencies(Package("", "A"))) == ["B", "C"]


def test_missing_file_reports_error(tmp_path):
    """Отсутствующий файл — ошибка."""
    with pytest.raises(TestRepositoryError):
        TestRepository.load(tmp_path / "no_such.txt")


def test_non_utf8_file_reports_error(tmp_path):
    """Файл не в UTF-8 — ошибка."""
    path = tmp_path / "repo.txt"
    path.write_bytes(b"A: \xff\n")

    with pytest.raises(TestRepositoryError):
        TestRepository.load(path)
