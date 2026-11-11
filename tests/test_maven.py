"""Тесты получения прямых зависимостей из репозитория Maven."""

from __future__ import annotations

import pytest

from depvis.maven import MavenRepository, RepositoryError, expand, parse_pom
from depvis.package import Package

URL = "https://repo.example.org/maven2"
APP = ("org.example", "app", "1.0")


def pom(body: str) -> str:
    """Обернуть содержимое в корневой элемент POM."""
    return (
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        "<modelVersion>4.0.0</modelVersion>" + body + "</project>"
    )


def dependency(artifact: str, extra: str = "") -> str:
    """Объявление зависимости из группы org.example."""
    return (
        "<dependency><groupId>org.example</groupId>"
        f"<artifactId>{artifact}</artifactId>{extra}</dependency>"
    )


def project(artifact: str, body: str) -> str:
    """POM пакета org.example с версией 1.0."""
    return pom(
        "<groupId>org.example</groupId>"
        f"<artifactId>{artifact}</artifactId><version>1.0</version>" + body
    )


def url_of(group: str, artifact: str, version: str) -> str:
    """Адрес POM в тестовом репозитории."""
    path = group.replace(".", "/")
    return f"{URL}/{path}/{artifact}/{version}/{artifact}-{version}.pom"


def coordinates(packages) -> list[str]:
    """Координаты пакетов списком строк."""
    return [package.coordinates for package in packages]


class FakeRepository(MavenRepository):
    """Репозиторий, отдающий заранее заданные файлы POM."""

    def __init__(self, files: dict[str, str]) -> None:
        """Запомнить файлы по их адресам."""
        super().__init__(URL)
        self.files = files
        self.requested: list[str] = []

    def download(self, url: str) -> bytes:
        """Отдать файл из набора или сообщить об ошибке 404."""
        self.requested.append(url)
        if url not in self.files:
            raise RepositoryError(f"{url}: HTTP 404 Not Found")
        return self.files[url].encode("utf-8")


@pytest.fixture
def repository():
    """Фабрика репозиториев из набора файлов POM."""

    def make(files: dict[tuple[str, str, str], str]) -> FakeRepository:
        """Создать репозиторий по координатам и содержимому POM."""
        return FakeRepository(
            {url_of(*key): text for key, text in files.items()}
        )

    return make


SIMPLE = project(
    "app",
    "<dependencies>"
    + dependency("core", "<version>2.0</version>")
    + dependency("tests", "<version>3.0</version><scope>test</scope>")
    + dependency("extra", "<version>4.0</version><optional>true</optional>")
    + dependency("server", "<version>5.0</version><scope>provided</scope>")
    + dependency("runtime", "<version>6.0</version><scope>runtime</scope>")
    + "</dependencies>",
)

PROPERTIES = project(
    "app",
    "<properties><core.version>2.5</core.version></properties>"
    "<dependencies>"
    + dependency("core", "<version>${core.version}</version>")
    + dependency("same", "<version>${project.version}</version>")
    + "</dependencies>",
)

PARENT = project(
    "parent",
    "<properties><log.version>2.0</log.version></properties>"
    "<dependencyManagement><dependencies>"
    + dependency("core", "<version>9.9</version>")
    + "</dependencies></dependencyManagement>"
    "<dependencies>"
    + dependency("log", "<version>${log.version}</version>")
    + "</dependencies>",
)

CHILD = pom(
    "<parent><groupId>org.example</groupId><artifactId>parent</artifactId>"
    "<version>1.0</version></parent><artifactId>app</artifactId>"
    "<dependencies>" + dependency("core") + "</dependencies>"
)

BOM = project(
    "bom",
    "<dependencyManagement><dependencies>"
    + dependency("core", "<version>7.1</version>")
    + "</dependencies></dependencyManagement>",
)

WITH_BOM = project(
    "app",
    "<dependencyManagement><dependencies>"
    + dependency("bom", "<version>1.0</version><type>pom</type>"
                 "<scope>import</scope>")
    + "</dependencies></dependencyManagement>"
    "<dependencies>" + dependency("core") + "</dependencies>",
)

DUPLICATE = project(
    "app",
    "<dependencies>"
    + dependency("core", "<version>1.1</version>")
    + dependency("core", "<version>1.2</version>")
    + "</dependencies>",
)


def test_pom_url_is_built_from_coordinates():
    """Адрес POM строится из координат пакета."""
    repository = MavenRepository("https://repo1.maven.org/maven2/")
    package = Package("org.apache.commons", "commons-lang3", "3.14.0")

    assert repository.pom_url(package) == (
        "https://repo1.maven.org/maven2/org/apache/commons/"
        "commons-lang3/3.14.0/commons-lang3-3.14.0.pom"
    )


def test_only_runtime_dependencies_are_returned(repository):
    """Зависимости test, provided и optional отбрасываются."""
    repo = repository({APP: SIMPLE})

    found = repo.dependencies(Package(*APP))

    assert coordinates(found) == [
        "org.example:core:2.0",
        "org.example:runtime:6.0",
    ]


def test_properties_are_substituted(repository):
    """Свойства ${...} подставляются в версии."""
    repo = repository({APP: PROPERTIES})

    found = repo.dependencies(Package(*APP))

    assert coordinates(found) == [
        "org.example:core:2.5",
        "org.example:same:1.0",
    ]


def test_parent_gives_properties_dependencies_and_versions(repository):
    """Родительский POM даёт свойства, зависимости и версии."""
    repo = repository({("org.example", "parent", "1.0"): PARENT, APP: CHILD})

    found = repo.dependencies(Package(*APP))

    assert coordinates(found) == [
        "org.example:core:9.9",
        "org.example:log:2.0",
    ]


def test_imported_bom_gives_versions(repository):
    """Версия берётся из импортированного BOM."""
    repo = repository({("org.example", "bom", "1.0"): BOM, APP: WITH_BOM})

    found = repo.dependencies(Package(*APP))

    assert coordinates(found) == ["org.example:core:7.1"]


def test_missing_bom_is_skipped(repository):
    """Недоступный BOM не мешает получить остальные зависимости."""
    repo = repository({APP: WITH_BOM})

    found = repo.dependencies(Package(*APP))

    assert coordinates(found) == ["org.example:core"]


def test_duplicate_declaration_is_taken_once(repository):
    """Повторное объявление зависимости учитывается один раз."""
    repo = repository({APP: DUPLICATE})

    found = repo.dependencies(Package(*APP))

    assert coordinates(found) == ["org.example:core:1.1"]


def test_pom_is_downloaded_once(repository):
    """Скачанный POM берётся из кэша."""
    repo = repository({APP: SIMPLE})
    package = Package(*APP)

    repo.dependencies(package)
    repo.dependencies(package)

    assert len(repo.requested) == 1


def test_missing_package_reports_error(repository):
    """Отсутствующий в репозитории пакет — ошибка."""
    with pytest.raises(RepositoryError) as info:
        repository({}).dependencies(Package(*APP))

    assert "404" in str(info.value)


def test_broken_pom_reports_error(repository):
    """Повреждённый POM — ошибка."""
    repo = repository({APP: "<project>"})

    with pytest.raises(RepositoryError) as info:
        repo.dependencies(Package(*APP))

    assert "не удалось разобрать POM" in str(info.value)


def test_package_without_version_reports_error():
    """Пакет без версии запросить нельзя."""
    with pytest.raises(RepositoryError):
        MavenRepository(URL).pom(Package("org.example", "app", ""))


def test_unknown_property_is_left_as_is():
    """Неизвестное свойство остаётся без изменений."""
    assert expand("${missing}", {}) == "${missing}"


def test_recursive_property_is_resolved():
    """Свойство, ссылающееся на другое свойство, раскрывается."""
    assert expand("${a}", {"a": "${b}", "b": "1.0"}) == "1.0"


def test_parse_pom_reads_parent():
    """groupId и версия наследуются от родителя."""
    parsed = parse_pom(CHILD.encode("utf-8"))

    assert parsed.parent == Package("org.example", "parent", "1.0")
    assert parsed.group == "org.example"
    assert parsed.version == "1.0"
