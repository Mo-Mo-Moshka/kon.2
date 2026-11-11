# Визуализатор графа зависимостей Maven (вариант 10)

Практическая работа по дисциплине «Конфигурационное управление».

## Общее описание

Инструмент строит и визуализирует граф зависимостей пакета Maven.
Готовые средства (менеджеры пакетов и сторонние библиотеки для
получения зависимостей) не используются: информация о зависимостях
извлекается самостоятельно.

Этапы работы:

1. **Минимальный прототип с конфигурацией** — CLI-приложение,
   настраиваемое через файл формата INI (текущий этап).
2. Сбор данных о прямых зависимостях пакета Maven.
3. Построение графа с учётом транзитивности (BFS без рекурсии).
4. Обратные зависимости.
5. Визуализация: Mermaid, PNG, ASCII-дерево.

## Структура репозитория

```
src/
  main.py               точка входа, вывод параметров
  depvis/
    config.py           чтение и проверка INI-конфигурации
    errors.py           ошибки приложения
config.ini              конфигурация по умолчанию
examples/
  test_mode.ini         пример работы с тестовым репозиторием
  test_repo.txt         описание тестового репозитория
  bad_*.ini             примеры ошибок в параметрах
tests/
  test_config.py        тесты конфигурации
  test_main.py          тесты точки входа
run.sh / run.bat        запуск приложения
pytest.ini              настройки pytest (путь к пакету src)
```

## Запуск

Требуется Python 3.10 или новее, сторонние зависимости не нужны.

```
python src/main.py
python src/main.py --config examples/test_mode.ini
```

Эквивалентно: `./run.sh` или `run.bat`.

Ключ `--config` (`-c`) задаёт путь к конфигурационному файлу,
по умолчанию берётся `config.ini` в текущем каталоге.

## Конфигурация

Единственный источник настраиваемых пользователем параметров —
файл формата INI.

```ini
[package]
name = org.apache.commons:commons-lang3
version = 3.14.0

[repository]
url = https://repo1.maven.org/maven2
test_mode = off
test_file = examples/test_repo.txt

[output]
image = graph.png
ascii_tree = on
```

| Параметр               | Назначение                                                    |
| ---------------------- | ------------------------------------------------------------- |
| `package.name`         | имя анализируемого пакета (`groupId:artifactId`)               |
| `package.version`      | версия пакета                                                  |
| `repository.url`       | URL-адрес репозитория Maven                                    |
| `repository.test_mode` | режим работы с тестовым репозиторием                           |
| `repository.test_file` | путь к файлу описания тестового репозитория                    |
| `output.image`         | имя сгенерированного файла с изображением графа (PNG)          |
| `output.ascii_tree`    | режим вывода зависимостей в формате ASCII-дерева               |

Логические параметры принимают значения `on`/`off`, `yes`/`no`,
`true`/`false`, `1`/`0`, `да`/`нет`.

В тестовом режиме вместо URL используется файл описания графа
репозитория, где пакеты названы большими латинскими буквами
(`examples/test_repo.txt`):

```
A: B C
B: D
C: D E
D:
E: A
```

## Этап 1. Вывод параметров

При запуске приложение выводит все настраиваемые пользователем
параметры в формате «ключ = значение».

```
$ python src/main.py
Параметры конфигурации:
  package.name         = org.apache.commons:commons-lang3
  package.version      = 3.14.0
  repository.url       = https://repo1.maven.org/maven2
  repository.test_mode = off
  repository.test_file = <не задан>
  output.image         = graph.png
  output.ascii_tree    = on
```

```
$ python src/main.py --config examples/test_mode.ini
Параметры конфигурации:
  package.name         = A
  package.version      = 1.0
  repository.url       = <не задан>
  repository.test_mode = on
  repository.test_file = examples\test_repo.txt
  output.image         = A.png
  output.ascii_tree    = on
```

## Обработка ошибок

Ошибки проверяются для всех параметров: сообщение называет параметр
и причину, приложение завершается с кодом возврата 1. В каталоге
`examples/` лежит по конфигурации на каждый случай.

| Файл                     | Сообщение                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------- |
| `bad_missing_name.ini`   | `package.name: обязательный параметр не задан`                                                 |
| `bad_name.ini`           | `package.name: ожидались координаты Maven вида groupId:artifactId, получено 'commons lang3'`   |
| `bad_version.ini`        | `package.version: недопустимая версия пакета: '../3.14'`                                       |
| `bad_url.ini`            | `repository.url: ожидался адрес вида http(s)://host/path, получено 'repo1.maven.org'`          |
| `bad_test_mode.ini`      | `repository.test_mode: ожидалось логическое значение (...), получено 'sometimes'`              |
| `bad_test_file.ini`      | `repository.test_file: файл не найден: examples\no_such_repo.txt`                              |
| `bad_image.ini`          | `output.image: изображение графа сохраняется в формате PNG, получено 'graph.jpeg'`             |
| `bad_ascii_tree.ini`     | `output.ascii_tree: ожидалось логическое значение (...), получено 'maybe'`                     |
| `bad_syntax.ini`         | `--config: некорректный формат INI: File contains no section headers...`                       |
| `bad_unknown_key.ini`    | `package.scope: неизвестный параметр, допустимы только: name, version`                         |

Также сообщается об отсутствующем файле конфигурации, об отсутствующей
обязательной секции, о пустом значении, о каталоге вместо файла и о
несуществующем каталоге для изображения графа.

```
$ python src/main.py --config examples/bad_url.ini
Ошибка конфигурации: repository.url: ожидался адрес вида http(s)://host/path, получено 'repo1.maven.org'
```

## Тесты

```
python -m pytest
```

49 тестов покрывают разбор корректной конфигурации, синонимы логических
значений, тестовый режим и сообщения об ошибках для каждого параметра.
