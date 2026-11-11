"""Точка входа инструмента визуализации графа зависимостей Maven.

Этап 2: приложение читает конфигурацию, обращается к репозиторию
Maven и выводит прямые зависимости заданного пакета.

При запуске ``python src/main.py`` каталог ``src`` автоматически
попадает в путь поиска модулей, поэтому пакет ``depvis`` доступен.
"""

from __future__ import annotations

import argparse
import sys

from depvis.config import Config, load_config
from depvis.errors import DepVisError
from depvis.maven import MavenRepository
from depvis.package import Package

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


def run(config: Config) -> None:
    """Вывести прямые зависимости пакета, заданного в конфигурации."""
    if config.test_mode:
        raise DepVisError(
            "работа с тестовым репозиторием появится на следующем этапе"
        )
    package = Package.parse(config.package_name, config.package_version)
    repository = MavenRepository(config.repository_url)
    dependencies = repository.dependencies(package)

    print(f"Прямые зависимости пакета {package}:")
    if not dependencies:
        print("  зависимостей нет")
    for dependency in dependencies:
        print(f"  {dependency}")


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
