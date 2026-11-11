"""Текстовое представление графа зависимостей на языке Mermaid."""

from __future__ import annotations

from .graph import Graph
from .package import Package

ROOT_STYLE = "fill:#fff6e6,stroke:#c86e1e,stroke-width:2px"
UNRESOLVED_STYLE = "fill:#f4f4f4,stroke:#999,stroke-dasharray:4"


def node_ids(graph: Graph) -> dict[Package, str]:
    """Короткие идентификаторы узлов диаграммы."""
    return {node: f"n{index}" for index, node in enumerate(graph.nodes)}


def escape(label: str) -> str:
    """Экранировать подпись узла."""
    return label.replace('"', "'")


def render(graph: Graph, direction: str = "TD") -> str:
    """Построить описание графа на языке диаграмм Mermaid."""
    ids = node_ids(graph)
    lines = [f"graph {direction}"]
    for node, identifier in ids.items():
        lines.append(f'    {identifier}["{escape(node.coordinates)}"]')
    for source in graph.nodes:
        for target in graph.children(source):
            lines.append(f"    {ids[source]} --> {ids[target]}")

    lines.append(f"    classDef root {ROOT_STYLE};")
    lines.append(f"    classDef unresolved {UNRESOLVED_STYLE};")
    lines.append(f"    class {ids[graph.root]} root;")
    unresolved = [ids[node] for node in graph.unresolved if node in ids]
    if unresolved:
        lines.append(f"    class {','.join(unresolved)} unresolved;")
    return "\n".join(lines)
