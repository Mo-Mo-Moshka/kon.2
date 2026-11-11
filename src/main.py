"""Точка входа инструмента визуализации графа зависимостей Maven.

Этап 3: приложение строит граф зависимостей с учётом транзитивности
обходом в ширину без рекурсии и выводит его на экран. Источником
данных служит репозиторий Maven или файл тестового репозитория.

При запуске ``python src/main.py`` каталог ``src`` автоматически
попадает в путь поиска модулей, поэтому пакет ``depvis`` доступен.
"""

from __future__ import annotations

import argparse
import sys

from depvis.config import Config, load_config
from depvis.errors import DepVisError
from depvis.graph import Graph, build_graph, find_cycles
from depvis.maven import MavenRepository
from depvis.package import Package
from depvis.testrepo import TestRepository

DEFAULT_CONFIG = "config.ini"


def build_parser() -> argparse.ArgumentParser:
    """Разбор аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depvis",
        description=(
            "Инструмент визуализации графа зависимостей пакетов Maven. "
            "Все настраиваемые параметры задаются в конфигурационном "
            "файле формата INI."
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG,
        metavar="ФАЙЛ",
        help=f"путь к конфигурационному файлу (по умолчанию {DEFAULT_CONFIG})",
    )
    return parser


def use_utf8() -> None:
    """Выводить текст в UTF-8, чтобы русские сообщения читались.

    Потоки, которые не поддерживают смену кодировки, остаются как есть.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            continue


def open_repository(config: Config):
    """Открыть источник данных: тестовый репозиторий или Maven."""
    if config.test_mode:
        return TestRepository.load(config.test_file)
    return MavenRepository(config.repository_url)


def root_package(config: Config, repository) -> Package:
    """Пакет, с которого начинается обход."""
    version = "" if config.test_mode else config.package_version
    package = Package.parse(config.package_name, version)
    if config.test_mode and not repository.has(package):
        raise DepVisError(
            f"пакет {package.name} не описан в тестовом репозитории "
            f"{config.test_file}"
        )
    return package


def print_graph(graph: Graph) -> None:
    """Вывести граф зависимостей на экран."""
    print(f"Граф зависимостей пакета {graph.root}")
    print(f"  пакетов: {len(graph.nodes)}, зависимостей: {graph.edge_count}")
    for node in graph.nodes:
        children = graph.children(node)
        targets = ", ".join(str(item) for item in children)
        print(f"  {node} -> {targets or 'зависимостей нет'}")

    cycles = find_cycles(graph)
    if cycles:
        print("Циклические зависимости:")
        for cycle in cycles:
            print("  " + " -> ".join(str(item) for item in cycle))

    if graph.unresolved:
        print("Не удалось получить зависимости:")
        for package, reason in graph.unresolved.items():
            print(f"  {package}: {reason}")


def run(config: Config) -> None:
    """Построить и вывести граф зависимостей пакета из конфигурации."""
    repository = open_repository(config)
    print_graph(build_graph(repository, root_package(config, repository)))


def main(argv: list[str] | None = None) -> int:
    """Запустить приложение. Возвращает код выхода процесса."""
    use_utf8()
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except DepVisError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return 1
    try:
        run(config)
    except DepVisError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
