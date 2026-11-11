"""Вывод зависимостей в формате ASCII-дерева."""

from __future__ import annotations

from .graph import Graph
from .package import Package

BRANCH = "├── "
LAST_BRANCH = "└── "
LINE = "│   "
SPACE = "    "
CYCLE_MARK = " (цикл)"
REPEAT_MARK = " (повтор)"

Item = tuple[Package, str, bool, tuple[Package, ...]]


def push(
    stack: list[Item],
    graph: Graph,
    node: Package,
    prefix: str,
    path: tuple[Package, ...],
) -> None:
    """Положить зависимости узла на стек в обратном порядке.

    Элемент стека: пакет, отступ, признак последнего потомка и
    ветвь от корня до родителя.
    """
    children = graph.children(node)
    for index in reversed(range(len(children))):
        last = index == len(children) - 1
        stack.append((children[index], prefix, last, path))


def render(graph: Graph) -> list[str]:
    """Построить ASCII-дерево зависимостей обходом без рекурсии.

    Узел раскрывается один раз: повторное вхождение помечается как
    повтор, а возврат к пакету из текущей ветви — как цикл.
    """
    lines = [graph.root.coordinates]
    expanded: set[Package] = {graph.root}
    stack: list[Item] = []
    push(stack, graph, graph.root, "", (graph.root,))

    while stack:
        node, prefix, last, path = stack.pop()
        head = f"{prefix}{LAST_BRANCH if last else BRANCH}{node}"
        if node in path:
            lines.append(head + CYCLE_MARK)
        elif node in expanded and graph.children(node):
            lines.append(head + REPEAT_MARK)
        else:
            lines.append(head)
            expanded.add(node)
            child_prefix = prefix + (SPACE if last else LINE)
            push(stack, graph, node, child_prefix, path + (node,))
    return lines
