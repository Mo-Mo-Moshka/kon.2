"""Координаты пакета Maven.

Имя пакета тестового репозитория состоит из больших латинских букв
(``TEST_NAME_RE``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import DepVisError

TEST_NAME_RE = re.compile(r"^[A-Z]+$")
NAME_PARTS = 2
NAME_AND_VERSION_PARTS = 3


class PackageError(DepVisError):
    """Некорректные координаты пакета."""


@dataclass(frozen=True, order=True)
class Package:
    """Пакет Maven: groupId, artifactId и версия.

    Пакет тестового репозитория хранится как пакет с пустым groupId:
    его имя состоит из больших латинских букв, а версия не используется.
    """

    group: str
    artifact: str
    version: str = ""

    @property
    def name(self) -> str:
        """Имя пакета без версии."""
        if self.group:
            return f"{self.group}:{self.artifact}"
        return self.artifact

    @property
    def coordinates(self) -> str:
        """Полные координаты пакета вместе с версией."""
        if self.version:
            return f"{self.name}:{self.version}"
        return self.name

    def __str__(self) -> str:
        """Пакет в виде строки — его полные координаты."""
        return self.coordinates

    @classmethod
    def parse(cls, text: str, version: str = "") -> Package:
        """Разобрать ``groupId:artifactId[:version]`` или тестовое имя."""
        value = text.strip()
        if not value:
            raise PackageError("пустое имя пакета")
        parts = value.split(":")
        if len(parts) == 1:
            if not TEST_NAME_RE.match(parts[0]):
                raise PackageError(f"некорректное имя пакета: {text!r}")
            return cls("", parts[0], version)
        if len(parts) == NAME_PARTS:
            group, artifact = parts
        elif len(parts) == NAME_AND_VERSION_PARTS:
            group, artifact, version = parts
        else:
            raise PackageError(f"некорректные координаты пакета: {text!r}")
        if not group or not artifact:
            raise PackageError(f"некорректные координаты пакета: {text!r}")
        return cls(group, artifact, version)

    def with_version(self, version: str) -> Package:
        """Тот же пакет с другой версией."""
        return Package(self.group, self.artifact, version)
