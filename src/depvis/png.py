"""Минимальный растровый холст и запись файла PNG.

Изображение собирается вручную: пиксели хранятся в массиве байтов,
файл PNG собирается из блоков IHDR, IDAT и IEND, данные сжимаются
модулем ``zlib``. Сторонние графические библиотеки не используются.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from . import font

Color = tuple[int, int, int]

WHITE: Color = (255, 255, 255)
BLACK: Color = (20, 20, 20)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BIT_DEPTH = 8
COLOR_TYPE_RGB = 2
FILTER_NONE = 0
COMPRESSION_LEVEL = 9


class Canvas:
    """Растровое изображение в формате RGB."""

    def __init__(
        self, width: int, height: int, background: Color = WHITE
    ) -> None:
        """Создать холст заданного размера, залитый цветом фона."""
        self.width = max(1, width)
        self.height = max(1, height)
        self.data = bytearray(bytes(background) * (self.width * self.height))

    def pixel(self, x: int, y: int, color: Color) -> None:
        """Закрасить один пиксель, если он попадает в холст."""
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.data[offset:offset + 3] = bytes(color)

    def fill_rect(
        self, x: int, y: int, width: int, height: int, color: Color
    ) -> None:
        """Закрасить прямоугольник."""
        row = bytes(color) * max(0, min(width, self.width - x))
        if not row:
            return
        for line in range(max(y, 0), min(y + height, self.height)):
            start = (line * self.width + max(x, 0)) * 3
            self.data[start:start + len(row)] = row

    def rect(
        self, x: int, y: int, width: int, height: int, color: Color
    ) -> None:
        """Нарисовать рамку прямоугольника толщиной два пикселя."""
        border = 2
        self.fill_rect(x, y, width, border, color)
        self.fill_rect(x, y + height - border, width, border, color)
        self.fill_rect(x, y, border, height, color)
        self.fill_rect(x + width - border, y, border, height, color)

    def line(
        self, start: tuple[int, int], end: tuple[int, int], color: Color
    ) -> None:
        """Нарисовать отрезок толщиной два пикселя алгоритмом Брезенхэма."""
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            self.fill_rect(x0, y0, 2, 2, color)
            if (x0, y0) == (x1, y1):
                return
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += step_x
            if doubled <= dx:
                error += dx
                y0 += step_y

    def arrow_head(
        self, start: tuple[int, int], end: tuple[int, int], color: Color
    ) -> None:
        """Нарисовать наконечник стрелки, направленной в точку ``end``."""
        size = 7
        length = max(
            1.0, ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        )
        dir_x = (end[0] - start[0]) / length
        dir_y = (end[1] - start[1]) / length
        for step in range(size + 1):
            half = int((size - step) / 2)
            center_x = end[0] - dir_x * (size - step)
            center_y = end[1] - dir_y * (size - step)
            for offset in range(-half, half + 1):
                self.pixel(
                    round(center_x - dir_y * offset),
                    round(center_y + dir_x * offset),
                    color,
                )

    def text(
        self, position: tuple[int, int], value: str, color: Color, scale: int
    ) -> None:
        """Написать строку растровым шрифтом с заданным масштабом."""
        cursor, top = position
        for symbol in value:
            for row, line in enumerate(font.glyph(symbol)):
                for column, point in enumerate(line):
                    if point == "#":
                        self.fill_rect(
                            cursor + column * scale,
                            top + row * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor += (font.WIDTH + 1) * scale

    def save(self, path: str | Path) -> Path:
        """Сохранить изображение в файл формата PNG.

        Перед каждой строкой пикселей записывается байт фильтра
        ``FILTER_NONE`` — строка хранится без преобразований.
        """
        stride = self.width * 3
        raw = bytearray()
        for row in range(self.height):
            raw.append(FILTER_NONE)
            raw += self.data[row * stride:(row + 1) * stride]

        header = struct.pack(
            ">IIBBBBB", self.width, self.height, BIT_DEPTH,
            COLOR_TYPE_RGB, 0, 0, 0,
        )
        content = (
            PNG_SIGNATURE
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), COMPRESSION_LEVEL))
            + chunk(b"IEND", b"")
        )
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path


def chunk(tag: bytes, payload: bytes) -> bytes:
    """Блок файла PNG вместе с длиной и контрольной суммой."""
    body = tag + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body))
    )
