"""Рисование графа зависимостей в файл PNG.

Подписи выводятся латиницей: растровый шрифт содержит только
латинские буквы, цифры и знаки препинания.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import font
from .graph import Graph, find_cycles
from .package import Package
from .png import Canvas, Color

SCALE = 2
PADDING = 8
GAP_X = 28
GAP_Y = 64
MARGIN = 28
TITLE_SCALE = 2

BACKGROUND: Color = (255, 255, 255)
TEXT: Color = (25, 30, 40)
BOX: Color = (247, 249, 252)
BORDER: Color = (60, 90, 150)
ROOT_BORDER: Color = (200, 110, 30)
ROOT_BOX: Color = (255, 246, 230)
EDGE: Color = (120, 130, 145)
CYCLE_EDGE: Color = (200, 60, 60)
UNRESOLVED_BORDER: Color = (150, 150, 150)


@dataclass
class Box:
    """Прямоугольник узла на изображении."""

    x: int
    y: int
    width: int
    height: int
    label: str

    @property
    def center_x(self) -> int:
        """Горизонтальная координата середины прямоугольника."""
        return self.x + self.width // 2

    @property
    def middle_y(self) -> int:
        """Вертикальная координата середины прямоугольника."""
        return self.y + self.height // 2

    @property
    def right(self) -> int:
        """Координата правой стороны прямоугольника."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Координата нижней стороны прямоугольника."""
        return self.y + self.height


def label_width(package: Package) -> int:
    """Ширина прямоугольника узла с подписью."""
    return font.text_width(package.coordinates, SCALE) + 2 * PADDING


def layers(graph: Graph) -> list[list[Package]]:
    """Разложить узлы по уровням обхода в ширину."""
    result: list[list[Package]] = []
    for node in graph.nodes:
        level = graph.depth.get(node, 0)
        while len(result) <= level:
            result.append([])
        result[level].append(node)
    return result


def layout(
    graph: Graph, title: str
) -> tuple[dict[Package, Box], int, int]:
    """Разместить узлы по уровням и вычислить размер изображения."""
    box_height = font.text_height(SCALE) + 2 * PADDING
    rows = layers(graph)
    widths = [
        sum(label_width(node) for node in row) + GAP_X * (len(row) - 1)
        for row in rows
    ]
    content_width = max([font.text_width(title, TITLE_SCALE), *widths])
    top = MARGIN + font.text_height(TITLE_SCALE) + GAP_Y // 2

    boxes: dict[Package, Box] = {}
    for index, row in enumerate(rows):
        y = top + index * (box_height + GAP_Y)
        x = MARGIN + (content_width - widths[index]) // 2
        for node in row:
            width = label_width(node)
            boxes[node] = Box(x, y, width, box_height, node.coordinates)
            x += width + GAP_X

    height = top + len(rows) * (box_height + GAP_Y) - GAP_Y + MARGIN
    return boxes, content_width + 2 * MARGIN, height


def cycle_edges(graph: Graph) -> set[tuple[Package, Package]]:
    """Рёбра, входящие в циклы."""
    edges: set[tuple[Package, Package]] = set()
    for cycle in find_cycles(graph):
        edges.update(zip(cycle, cycle[1:]))
    return edges


def edge_ends(
    source: Box, target: Box
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Точки начала и конца стрелки между двумя узлами."""
    if target.y >= source.bottom:
        return (source.center_x, source.bottom), (target.center_x, target.y)
    if target.bottom <= source.y:
        return (source.center_x, source.y), (target.center_x, target.bottom)
    if target.x >= source.x:
        return (source.right, source.middle_y), (target.x, target.middle_y)
    return (source.x, source.middle_y), (target.right, target.middle_y)


def draw_edges(canvas: Canvas, graph: Graph, boxes: dict) -> None:
    """Нарисовать стрелки всех рёбер; рёбра циклов — красным."""
    cycled = cycle_edges(graph)
    for source in graph.nodes:
        for target in graph.children(source):
            color = CYCLE_EDGE if (source, target) in cycled else EDGE
            start, end = edge_ends(boxes[source], boxes[target])
            canvas.line(start, end, color)
            canvas.arrow_head(start, end, color)


def node_colors(graph: Graph, node: Package) -> tuple[Color, Color]:
    """Цвет заливки и рамки узла."""
    if node == graph.root:
        return ROOT_BOX, ROOT_BORDER
    if node in graph.unresolved:
        return BOX, UNRESOLVED_BORDER
    return BOX, BORDER


def render(graph: Graph, path: str | Path, title: str = "") -> Path:
    """Нарисовать граф зависимостей и сохранить его в файл PNG."""
    caption = title or f"Dependency graph: {graph.root.coordinates}"
    caption = caption.encode("ascii", "replace").decode("ascii")
    boxes, width, height = layout(graph, caption)
    canvas = Canvas(width, height, BACKGROUND)
    canvas.text((MARGIN, MARGIN), caption, TEXT, TITLE_SCALE)
    draw_edges(canvas, graph, boxes)

    for node, box in boxes.items():
        fill, border = node_colors(graph, node)
        canvas.fill_rect(box.x, box.y, box.width, box.height, fill)
        canvas.rect(box.x, box.y, box.width, box.height, border)
        canvas.text(
            (box.x + PADDING, box.y + PADDING), box.label, TEXT, SCALE
        )
    return canvas.save(path)
