"""Тесты визуализации: Mermaid, ASCII-дерево и изображение PNG."""

from __future__ import annotations

import struct
import zlib

from depvis import image, mermaid, tree
from depvis.graph import build_graph
from depvis.package import Package
from depvis.png import PNG_SIGNATURE, Canvas
from depvis.testrepo import TestRepository

DIAMOND = "A: B C\nB: D\nC: D\nD:\n"


def pkg(name: str) -> Package:
    """Пакет тестового репозитория."""
    return Package("", name)


def graph_of(text: str):
    """Граф тестового репозитория, построенный от пакета A."""
    repository = TestRepository.parse(text, "repo.txt")
    return build_graph(repository, pkg("A"))


def test_mermaid_lists_nodes_and_edges():
    """Описание Mermaid содержит узлы, рёбра и стиль корня."""
    lines = mermaid.render(graph_of("A: B C\nB: D\nC:\nD:\n")).splitlines()

    assert lines[0] == "graph TD"
    assert '    n0["A"]' in lines
    assert "    n0 --> n1" in lines
    assert "    n1 --> n3" in lines
    assert "    class n0 root;" in lines


def test_mermaid_marks_unresolved_packages():
    """Пакеты с неизвестными зависимостями отмечаются отдельно."""
    text = mermaid.render(graph_of("A: B\n"))

    assert text.splitlines()[-1] == "    class n1 unresolved;"


def test_mermaid_direction_can_be_changed():
    """Направление диаграммы задаётся параметром."""
    assert mermaid.render(graph_of("A:\n"), "LR").startswith("graph LR")


def test_tree_shows_branches():
    """Дерево рисует ветви и отступы."""
    lines = tree.render(graph_of("A: B C\nB: D\nC:\nD:\n"))

    assert lines == ["A", "├── B", "│   └── D", "└── C"]


def test_tree_marks_cycle():
    """Возврат к пакету текущей ветви помечается как цикл."""
    lines = tree.render(graph_of("A: B\nB: C\nC: A\n"))

    assert lines[-1].endswith("A (цикл)")


def test_tree_marks_repeated_subtree():
    """Повторно встреченное поддерево не раскрывается."""
    lines = tree.render(graph_of("A: B C\nB: D\nC: D\nD: E\nE:\n"))

    assert "    └── D (повтор)" in lines


def test_png_file_has_correct_header_and_size(tmp_path):
    """Файл PNG начинается с подписи и хранит размеры холста."""
    width, height = 40, 20
    canvas = Canvas(width, height)
    canvas.fill_rect(5, 5, 10, 10, (0, 0, 0))

    data = canvas.save(tmp_path / "picture.png").read_bytes()

    assert data.startswith(PNG_SIGNATURE)
    assert struct.unpack(">II", data[16:24]) == (width, height)


def test_png_pixels_can_be_read_back(tmp_path):
    """Закрашенный пиксель читается из сжатых данных IDAT."""
    width, color = 8, (10, 20, 30)
    canvas = Canvas(width, 4)
    canvas.pixel(2, 1, color)

    content = canvas.save(tmp_path / "picture.png").read_bytes()
    start = content.index(b"IDAT") + len(b"IDAT")
    length = struct.unpack(">I", content[start - 8:start - 4])[0]
    raw = zlib.decompress(content[start:start + length])

    offset = (width * 3 + 1) * 1 + 1 + 2 * 3
    assert raw[offset:offset + 3] == bytes(color)


def test_image_is_rendered_for_graph(tmp_path):
    """Граф рисуется в файл PNG."""
    path = image.render(graph_of(DIAMOND), tmp_path / "graph.png")

    assert path.read_bytes().startswith(PNG_SIGNATURE)


def test_layout_places_every_node():
    """Каждый узел получает место, уровни идут сверху вниз."""
    graph = graph_of(DIAMOND)

    boxes, width, height = image.layout(graph, "title")

    assert set(boxes) == set(graph.nodes)
    assert width > 0 and height > 0
    assert boxes[pkg("A")].y < boxes[pkg("B")].y < boxes[pkg("D")].y


def test_edges_between_nodes_of_one_level():
    """Ребро внутри одного уровня соединяет боковые стороны."""
    left = image.Box(0, 0, 10, 10, "A")
    right = image.Box(20, 0, 10, 10, "B")

    assert image.edge_ends(left, right) == ((10, 5), (20, 5))
    assert image.edge_ends(right, left) == ((20, 5), (10, 5))


def test_cycle_edges_are_detected():
    """Рёбра циклов находятся для подсветки."""
    edges = image.cycle_edges(graph_of("A: B\nB: A\n"))

    assert edges == {(pkg("A"), pkg("B")), (pkg("B"), pkg("A"))}
