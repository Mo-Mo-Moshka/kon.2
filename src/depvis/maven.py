"""Получение зависимостей пакета из репозитория Maven.

Менеджеры пакетов и сторонние библиотеки не используются: файл POM
скачивается по HTTP и разбирается средствами стандартной библиотеки.

В граф попадают зависимости областей видимости из ``RUNTIME_SCOPES``.
``MAX_PARENTS`` ограничивает длину цепочки родительских POM и число
импортов BOM.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from xml.etree import ElementTree

from .errors import DepVisError
from .package import Package

RUNTIME_SCOPES = frozenset({"", "compile", "runtime"})
MAX_PARENTS = 16
MAX_EXPANSIONS = 8
PROPERTY_RE = re.compile(r"\$\{([^}]+)\}")
USER_AGENT = "depvis/1.0 (coursework dependency visualizer)"


class RepositoryError(DepVisError):
    """Не удалось получить данные из репозитория."""


@dataclass
class Dependency:
    """Объявление зависимости внутри POM."""

    group: str
    artifact: str
    version: str = ""
    scope: str = ""
    optional: str = ""
    kind: str = "jar"

    @property
    def is_import(self) -> bool:
        """Импорт BOM внутри ``dependencyManagement``."""
        return self.scope == "import" and self.kind == "pom"


@dataclass
class Pom:
    """Содержимое одного файла POM."""

    group: str = ""
    artifact: str = ""
    version: str = ""
    parent: Package | None = None
    properties: dict[str, str] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    managed: list[Dependency] = field(default_factory=list)


def text_of(element: ElementTree.Element | None) -> str:
    """Текст элемента без лишних пробелов."""
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def local_name(tag: str) -> str:
    """Имя тега без пространства имён."""
    return tag.rsplit("}", 1)[-1]


def child(
    element: ElementTree.Element, name: str
) -> ElementTree.Element | None:
    """Дочерний элемент с заданным именем."""
    for item in element:
        if local_name(item.tag) == name:
            return item
    return None


def children(
    element: ElementTree.Element, name: str
) -> list[ElementTree.Element]:
    """Все дочерние элементы с заданным именем."""
    return [item for item in element if local_name(item.tag) == name]


def child_text(element: ElementTree.Element, name: str) -> str:
    """Текст дочернего элемента с заданным именем."""
    return text_of(child(element, name))


def parse_dependencies(
    parent: ElementTree.Element | None,
) -> list[Dependency]:
    """Разобрать список ``<dependency>``."""
    if parent is None:
        return []
    return [
        Dependency(
            group=child_text(node, "groupId"),
            artifact=child_text(node, "artifactId"),
            version=child_text(node, "version"),
            scope=child_text(node, "scope"),
            optional=child_text(node, "optional"),
            kind=child_text(node, "type") or "jar",
        )
        for node in children(parent, "dependency")
    ]


def parse_parent(root: ElementTree.Element) -> Package | None:
    """Координаты родительского POM."""
    node = child(root, "parent")
    if node is None:
        return None
    return Package(
        child_text(node, "groupId"),
        child_text(node, "artifactId"),
        child_text(node, "version"),
    )


def parse_pom(data: bytes, source: str = "") -> Pom:
    """Разобрать содержимое файла POM."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise RepositoryError(
            f"не удалось разобрать POM {source}: {exc}"
        ) from exc

    pom = Pom(
        group=child_text(root, "groupId"),
        artifact=child_text(root, "artifactId"),
        version=child_text(root, "version"),
        parent=parse_parent(root),
    )
    if pom.parent is not None:
        pom.group = pom.group or pom.parent.group
        pom.version = pom.version or pom.parent.version

    properties = child(root, "properties")
    if properties is not None:
        for node in properties:
            pom.properties[local_name(node.tag)] = text_of(node)

    pom.dependencies = parse_dependencies(child(root, "dependencies"))
    management = child(root, "dependencyManagement")
    if management is not None:
        pom.managed = parse_dependencies(child(management, "dependencies"))
    return pom


def expand(value: str, properties: dict[str, str]) -> str:
    """Подставить значения свойств вида ``${property}``."""
    result = value
    for _ in range(MAX_EXPANSIONS):
        replaced = PROPERTY_RE.sub(
            lambda found: properties.get(found.group(1), found.group(0)),
            result,
        )
        if replaced == result:
            break
        result = replaced
    return result


def collect_managed(
    entries: list[Dependency],
    properties: dict[str, str],
    versions: dict[str, str],
    imports: list[tuple[Package, dict[str, str]]],
    override: bool,
) -> None:
    """Добавить версии из ``dependencyManagement`` и найти импорты BOM.

    :param override: заменять ли уже известные версии.
    """
    for entry in entries:
        group = expand(entry.group, properties)
        artifact = expand(entry.artifact, properties)
        version = expand(entry.version, properties)
        if not version:
            continue
        if entry.is_import:
            imports.append((Package(group, artifact, version), properties))
            continue
        key = f"{group}:{artifact}"
        if override or key not in versions:
            versions[key] = version


class MavenRepository:
    """Репозиторий Maven, доступный по URL-адресу."""

    def __init__(self, url: str, timeout: float = 20.0) -> None:
        """Запомнить адрес репозитория и подготовить кэш POM."""
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._poms: dict[Package, Pom] = {}

    def pom_url(self, package: Package) -> str:
        """Адрес файла POM для пакета."""
        group_path = package.group.replace(".", "/")
        name = f"{package.artifact}-{package.version}.pom"
        return (
            f"{self.url}/{group_path}/{package.artifact}/"
            f"{package.version}/{name}"
        )

    def download(self, url: str) -> bytes:
        """Скачать файл по HTTP."""
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RepositoryError(
                f"{url}: HTTP {exc.code} {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RepositoryError(
                f"{url}: нет связи с репозиторием ({exc.reason})"
            ) from exc
        except OSError as exc:
            raise RepositoryError(f"{url}: ошибка загрузки ({exc})") from exc

    def pom(self, package: Package) -> Pom:
        """Файл POM пакета (с кэшированием в памяти)."""
        cached = self._poms.get(package)
        if cached is not None:
            return cached
        if not package.version:
            raise RepositoryError(f"не задана версия пакета {package.name}")
        url = self.pom_url(package)
        pom = parse_pom(self.download(url), url)
        self._poms[package] = pom
        return pom

    def chain(self, package: Package) -> list[Pom]:
        """POM пакета и цепочка его родителей, от потомка к предку."""
        result: list[Pom] = []
        current: Package | None = package
        seen: set[Package] = set()
        while current is not None and len(result) < MAX_PARENTS:
            if current in seen:
                break
            seen.add(current)
            pom = self.pom(current)
            result.append(pom)
            current = pom.parent
        return result

    def properties(
        self, package: Package, chain: list[Pom]
    ) -> dict[str, str]:
        """Свойства пакета: от предков к потомку, потомок главнее."""
        properties: dict[str, str] = {}
        for pom in reversed(chain):
            properties.update(pom.properties)
        head = chain[0]
        version = head.version or package.version
        group = head.group or package.group
        implicit = {
            "project.version": version,
            "project.groupId": group,
            "project.artifactId": head.artifact or package.artifact,
            "pom.version": version,
            "pom.groupId": group,
            "version": version,
        }
        if head.parent is not None:
            implicit["project.parent.version"] = head.parent.version
            implicit["project.parent.groupId"] = head.parent.group
        for key, value in implicit.items():
            properties.setdefault(key, value)
        return properties

    def managed_versions(
        self, chain: list[Pom], properties: dict[str, str]
    ) -> dict[str, str]:
        """Версии из ``dependencyManagement``, включая импорты BOM."""
        versions: dict[str, str] = {}
        imports: list[tuple[Package, dict[str, str]]] = []
        for pom in reversed(chain):
            collect_managed(
                pom.managed, properties, versions, imports, override=True
            )
        self.import_boms(imports, versions)
        return versions

    def import_boms(
        self,
        imports: list[tuple[Package, dict[str, str]]],
        versions: dict[str, str],
    ) -> None:
        """Добавить версии из импортированных BOM, не заменяя известные."""
        processed = 0
        while imports and processed < MAX_PARENTS:
            processed += 1
            package, outer = imports.pop(0)
            try:
                bom_chain = self.chain(package)
            except RepositoryError:
                continue
            bom_properties = dict(outer)
            bom_properties.update(self.properties(package, bom_chain))
            for pom in reversed(bom_chain):
                collect_managed(
                    pom.managed,
                    bom_properties,
                    versions,
                    imports,
                    override=False,
                )

    def dependencies(self, package: Package) -> list[Package]:
        """Прямые зависимости пакета.

        Учитываются зависимости, унаследованные от родительских POM,
        подстановка свойств и версии из ``dependencyManagement``.
        Зависимости области ``test``, ``provided``, ``system`` и
        необязательные зависимости в граф не попадают.
        """
        chain = self.chain(package)
        properties = self.properties(package, chain)
        managed = self.managed_versions(chain, properties)

        result: list[Package] = []
        seen: set[str] = set()
        for pom in chain:
            for entry in pom.dependencies:
                found = resolve(entry, properties, managed)
                if found is not None and found.name not in seen:
                    seen.add(found.name)
                    result.append(found)
        return result


def resolve(
    entry: Dependency, properties: dict[str, str], managed: dict[str, str]
) -> Package | None:
    """Пакет зависимости или ``None``, если она не попадает в граф."""
    group = expand(entry.group, properties)
    artifact = expand(entry.artifact, properties)
    if not group or not artifact:
        return None
    if expand(entry.scope, properties) not in RUNTIME_SCOPES:
        return None
    if expand(entry.optional, properties).lower() == "true":
        return None
    version = expand(entry.version, properties)
    if not version:
        version = managed.get(f"{group}:{artifact}", "")
    if PROPERTY_RE.search(version):
        version = ""
    return Package(group, artifact, version)
