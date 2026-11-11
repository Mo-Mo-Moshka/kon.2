"""Тестовый репозиторий, описанный текстовым файлом.

Файл описывает граф репозитория: в каждой строке указан пакет и его
прямые зависимости. Пакеты называются большими латинскими буквами.

```
A: B C
B: D
C:
```
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import DepVisError
from .package import Package

NAME_RE = re.compile(r"^[A-Z]+$")
COMMENT_PREFIXES = ("#", ";")


class TestRepositoryError(DepVisError):
    """Ошибка в файле описания тестового репозитория.

    Атрибут ``__test__`` сообщает pytest, что это не набор тестов.
    """

    __test__ = False


class TestRepository:
    """Репозиторий, прочитанный из файла описания графа.

    Атрибут ``__test__`` сообщает pytest, что это не набор тестов.
    """

    __test__ = False

    def __init__(self, edges: dict[str, list[str]], source: str = "") -> None:
        """Запомнить рёбра графа и имя файла-источника."""
        self.edges = edges
        self.source = source

    @classmethod
    def load(cls, path: str | Path) -> TestRepository:
        """Прочитать файл описания тестового репозитория."""
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise TestRepositoryError(
                f"{file_path}: файл должен быть в кодировке UTF-8 "
                f"({exc.reason})"
            ) from exc
        except OSError as exc:
            raise TestRepositoryError(
                f"{file_path}: не удалось прочитать ({exc})"
            ) from exc
        return cls.parse(text, str(file_path))

    @classmethod
    def parse(cls, text: str, source: str = "") -> TestRepository:
        """Разобрать описание графа репозитория."""
        edges: dict[str, list[str]] = {}
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith(COMMENT_PREFIXES):
                continue
            where = f"{source}, строка {number}"
            name, dependencies = parse_line(line, where)
            if name in edges:
                raise TestRepositoryError(
                    f"{where}: пакет {name} описан повторно"
                )
            edges[name] = dependencies

        if not edges:
            raise TestRepositoryError(
                f"{source}: файл не содержит ни одного пакета"
            )
        return cls(edges, source)

    def has(self, package: Package) -> bool:
        """Описан ли пакет в файле."""
        return package.artifact in self.edges

    def packages(self) -> list[Package]:
        """Все пакеты: описанные и упомянутые как зависимости."""
        names: list[str] = []
        for name, dependencies in self.edges.items():
            for item in [name, *dependencies]:
                if item not in names:
                    names.append(item)
        return [Package("", name) for name in names]

    def dependencies(self, package: Package) -> list[Package]:
        """Прямые зависимости пакета."""
        name = package.artifact
        if name not in self.edges:
            raise TestRepositoryError(
                f"пакет {name} не описан в тестовом репозитории "
                f"{self.source}"
            )
        return [Package("", item) for item in self.edges[name]]


def parse_line(line: str, where: str) -> tuple[str, list[str]]:
    """Разобрать строку вида ``A: B C``."""
    if ":" not in line:
        raise TestRepositoryError(
            f"{where}: ожидалась запись вида 'A: B C', получено {line!r}"
        )
    name, _, rest = line.partition(":")
    name = name.strip()
    if not NAME_RE.match(name):
        raise TestRepositoryError(
            f"{where}: имя пакета состоит из больших латинских букв, "
            f"получено {name!r}"
        )
    dependencies: list[str] = []
    for item in rest.replace(",", " ").split():
        if not NAME_RE.match(item):
            raise TestRepositoryError(
                f"{where}: имя зависимости состоит из больших латинских "
                f"букв, получено {item!r}"
            )
        if item not in dependencies:
            dependencies.append(item)
    return name, dependencies
