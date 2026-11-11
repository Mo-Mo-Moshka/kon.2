"""Построение графа зависимостей и операции над ним.

Граф строится обходом в ширину (BFS) без рекурсии: очередь пакетов
и множество уже посещённых узлов. Повторный заход в посещённый узел
не выполняется, поэтому циклические зависимости не приводят к
зацикливанию — они остаются в графе как рёбра и отмечаются отдельно.

``MAX_NODES`` защищает от бесконечного роста графа.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .errors import DepVisError
from .package import Package

MAX_NODES = 1000


class GraphError(DepVisError):
    """Ошибка построения графа зависимостей."""


@dataclass
class Graph:
    """Граф зависимостей: узлы в порядке обхода и рёбра между ними.

    ``unresolved`` хранит пакеты, данные о которых получить не удалось,
    и причину.
    """

    root: Package
    nodes: list[Package] = field(default_factory=list)
    edges: dict[Package, list[Package]] = field(default_factory=dict)
    depth: dict[Package, int] = field(default_factory=dict)
    unresolved: dict[Package, str] = field(default_factory=dict)

    def add_node(self, package: Package, depth: int = 0) -> None:
        """Добавить узел, если его ещё нет."""
        if package in self.edges:
            return
        self.nodes.append(package)
        self.edges[package] = []
        self.depth[package] = depth

    def add_edge(self, source: Package, target: Package) -> None:
        """Добавить ребро «пакет — его зависимость»."""
        self.add_node(source)
        if target not in self.edges[source]:
            self.edges[source].append(target)

    def children(self, package: Package) -> list[Package]:
        """Зависимости пакета."""
        return self.edges.get(package, [])

    @property
    def edge_count(self) -> int:
        """Количество рёбер графа."""
        return sum(len(targets) for targets in self.edges.values())


def build_graph(
    repository, root: Package, max_nodes: int = MAX_NODES
) -> Graph:
    """Построить граф зависимостей пакета обходом в ширину без рекурсии.

    :param repository: источник данных с методом ``dependencies``.
    :param root: пакет, с которого начинается обход; если его
        зависимости получить нельзя, ошибка передаётся дальше.
    """
    graph = Graph(root=root)
    graph.add_node(root, depth=0)
    queue: deque[Package] = deque([root])
    visited: set[Package] = {root}

    while queue:
        current = queue.popleft()
        try:
            dependencies = repository.dependencies(current)
        except DepVisError as error:
            if current == root:
                raise
            graph.unresolved[current] = str(error)
            continue
        for dependency in dependencies:
            if dependency not in visited:
                visit(graph, current, dependency, max_nodes)
                visited.add(dependency)
                if dependency not in graph.unresolved:
                    queue.append(dependency)
            graph.add_edge(current, dependency)

    return graph


def visit(
    graph: Graph, parent: Package, package: Package, max_nodes: int
) -> None:
    """Добавить в граф впервые встреченный пакет."""
    if len(graph.nodes) >= max_nodes:
        raise GraphError(f"граф слишком большой: более {max_nodes} пакетов")
    graph.add_node(package, graph.depth[parent] + 1)
    if package.group and not package.version:
        graph.unresolved[package] = "версия зависимости не определена"


class ReverseView:
    """Источник данных, отдающий обратные зависимости пакета.

    Подставляется в :func:`build_graph` вместо репозитория, поэтому
    обратные зависимости строятся тем же обходом в ширину.
    """

    def __init__(self, parents: dict[Package, list[Package]]) -> None:
        """Запомнить для каждого пакета список зависящих от него."""
        self.parents = parents

    def has(self, package: Package) -> bool:
        """Известен ли пакет."""
        return package in self.parents

    def dependencies(self, package: Package) -> list[Package]:
        """Пакеты, которые зависят от данного."""
        return list(self.parents.get(package, []))


def reverse_view(repository, packages: list[Package]) -> ReverseView:
    """Построить обратные связи для перечисленных пакетов.

    Пакеты, зависимости которых получить не удалось, пропускаются.
    """
    parents: dict[Package, list[Package]] = {
        package: [] for package in packages
    }
    for package in packages:
        try:
            dependencies = repository.dependencies(package)
        except DepVisError:
            continue
        for dependency in dependencies:
            users = parents.setdefault(dependency, [])
            if package not in users:
                users.append(package)
    return ReverseView(parents)


def find_cycles(graph: Graph) -> list[list[Package]]:
    """Найти циклические зависимости обходом в глубину без рекурсии.

    Возвращает список циклов; каждый цикл начинается и заканчивается
    одним и тем же пакетом.
    """
    cycles: list[list[Package]] = []
    known: set[tuple[Package, ...]] = set()
    finished: set[Package] = set()
    for start in graph.nodes:
        if start not in finished:
            for cycle in walk(graph, start, finished):
                key = canonical(cycle)
                if key not in known:
                    known.add(key)
                    cycles.append(cycle)
    return cycles


def walk(
    graph: Graph, start: Package, finished: set[Package]
) -> list[list[Package]]:
    """Обойти граф в глубину от ``start`` на явном стеке.

    Стек хранит для каждого узла текущего пути ещё не просмотренные
    зависимости. Возврат к узлу текущего пути означает цикл.
    """
    cycles: list[list[Package]] = []
    path: list[Package] = [start]
    stack: list[list[Package]] = [list(graph.children(start))]
    while stack:
        pending = stack[-1]
        if not pending:
            finished.add(path.pop())
            stack.pop()
            continue
        node = pending.pop(0)
        if node in path:
            cycles.append(path[path.index(node):] + [node])
        elif node not in finished:
            path.append(node)
            stack.append(list(graph.children(node)))
    return cycles


def canonical(cycle: list[Package]) -> tuple[Package, ...]:
    """Представление цикла, не зависящее от точки входа в него."""
    body = cycle[:-1]
    if not body:
        return tuple(cycle)
    smallest = min(
        range(len(body)), key=lambda index: body[index].coordinates
    )
    return tuple(body[smallest:] + body[:smallest])
