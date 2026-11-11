"""Тесты построения графа зависимостей."""

from __future__ import annotations

import pytest

from depvis.graph import (
    GraphError,
    build_graph,
    find_cycles,
    reverse_view,
)
from depvis.package import Package
from depvis.testrepo import TestRepository, TestRepositoryError


def pkg(name: str) -> Package:
    """Пакет тестового репозитория."""
    return Package("", name)


def names(packages) -> list[str]:
    """Имена пакетов списком строк."""
    return [package.name for package in packages]


def graph_of(text: str, root: str = "A", **options):
    """Граф тестового репозитория, построенный от пакета ``root``."""
    repository = TestRepository.parse(text, "repo.txt")
    return build_graph(repository, pkg(root), **options)


def cycles_of(text: str) -> list[list[str]]:
    """Циклы графа тестового репозитория в виде списков имён."""
    return [names(cycle) for cycle in find_cycles(graph_of(text))]


def test_graph_is_built_in_breadth_first_order():
    """Узлы идут в порядке обхода в ширину, уровни считаются."""
    graph = graph_of("A: B C\nB: D\nC: E\nD:\nE:\n")

    assert names(graph.nodes) == ["A", "B", "C", "D", "E"]
    assert [graph.depth[node] for node in graph.nodes] == [0, 1, 1, 2, 2]
    assert graph.edge_count == len(["AB", "AC", "BD", "CE"])


def test_shared_dependency_is_one_node():
    """Общая зависимость — один узел с двумя входящими рёбрами."""
    graph = graph_of("A: B C\nB: D\nC: D\nD:\n")

    assert names(graph.nodes) == ["A", "B", "C", "D"]
    assert names(graph.children(pkg("B"))) == ["D"]
    assert names(graph.children(pkg("C"))) == ["D"]


def test_cycle_does_not_hang_and_is_reported():
    """Цикл не зацикливает обход и попадает в список циклов."""
    text = "A: B\nB: C\nC: A\n"

    assert names(graph_of(text).nodes) == ["A", "B", "C"]
    assert cycles_of(text) == [["A", "B", "C", "A"]]


def test_self_dependency_is_reported():
    """Пакет, зависящий от себя, образует цикл."""
    assert cycles_of("A: A\n") == [["A", "A"]]


def test_two_cycles_are_reported_once_each():
    """Каждый цикл выводится один раз."""
    found = sorted(cycles_of("A: B D\nB: C\nC: A\nD: E\nE: D\n"))

    assert found == [["A", "B", "C", "A"], ["D", "E", "D"]]


def test_graph_without_cycles_reports_none():
    """В ромбе без циклов циклов не находится."""
    assert cycles_of("A: B C\nB: D\nC: D\nD:\n") == []


def test_unknown_dependency_is_left_unresolved():
    """Неописанная зависимость остаётся листом с причиной."""
    graph = graph_of("A: B C\nB:\n")

    assert names(graph.nodes) == ["A", "B", "C"]
    assert names(graph.unresolved) == ["C"]
    assert graph.children(pkg("C")) == []


def test_unavailable_root_reports_error():
    """Недоступный корневой пакет — ошибка."""
    with pytest.raises(TestRepositoryError):
        graph_of("B: C\nC:\n")


def test_too_large_graph_reports_error():
    """Слишком большой граф — ошибка."""
    chain = "\n".join(
        f"{chr(ord('A') + index)}: {chr(ord('B') + index)}"
        for index in range(len("ABCDEFGHIJ"))
    )

    with pytest.raises(GraphError):
        graph_of(chain, max_nodes=len("ABC"))


class VersionlessRepository:
    """Репозиторий, где у зависимости не определена версия."""

    def dependencies(self, package: Package) -> list[Package]:
        """Корень зависит от пакета без версии."""
        if package.artifact == "app":
            return [Package("org.example", "core", "")]
        raise AssertionError("пакет без версии запрашиваться не должен")


def test_dependency_without_version_is_not_requested():
    """Зависимость без версии остаётся листом и не запрашивается."""
    root = Package("org.example", "app", "1.0")

    graph = build_graph(VersionlessRepository(), root)

    assert names(graph.unresolved) == ["org.example:core"]


def reverse_of(text: str, name: str):
    """Граф обратных зависимостей пакета ``name``."""
    repository = TestRepository.parse(text, "repo.txt")
    view = reverse_view(repository, repository.packages())
    return build_graph(view, pkg(name))


def test_reverse_view_lists_dependents():
    """Обратные связи перечисляют зависящие пакеты."""
    repository = TestRepository.parse("A: B C\nB: D\nC: D\nD:\n", "r")

    view = reverse_view(repository, repository.packages())

    assert names(view.dependencies(pkg("D"))) == ["B", "C"]
    assert view.dependencies(pkg("A")) == []
    assert view.has(pkg("D")) is True
    assert view.has(pkg("Z")) is False


def test_reverse_graph_uses_the_same_traversal():
    """Обратные зависимости обходятся тем же BFS."""
    graph = reverse_of("A: B\nB: C\nC:\nD: C\n", "C")

    assert names(graph.nodes) == ["C", "B", "D", "A"]
    assert names(graph.children(pkg("C"))) == ["B", "D"]
    assert names(graph.children(pkg("B"))) == ["A"]


def test_reverse_graph_handles_cycles():
    """Цикл среди обратных зависимостей не зацикливает обход."""
    graph = reverse_of("A: B\nB: C\nC: A\n", "A")

    assert names(graph.nodes) == ["A", "C", "B"]
    assert [names(cycle) for cycle in find_cycles(graph)] == [
        ["A", "C", "B", "A"]
    ]


def test_undeclared_package_is_skipped_in_reverse_view():
    """Неописанный пакет не мешает построить обратные связи."""
    graph = reverse_of("A: B\n", "B")

    assert names(graph.nodes) == ["B", "A"]
