# Визуализатор графа зависимостей Maven (вариант 10)

Практическая работа по дисциплине «Конфигурационное управление».

## Общее описание

Инструмент строит и визуализирует граф зависимостей пакета Maven.
Готовые средства (менеджеры пакетов и сторонние библиотеки для
получения зависимостей) не используются: информация о зависимостях
извлекается самостоятельно.

Этапы работы:

1. **Минимальный прототип с конфигурацией** — CLI-приложение,
   настраиваемое через файл формата INI.
2. **Сбор данных** — прямые зависимости пакета Maven.
3. **Основные операции** — граф с учётом транзитивности, обход в
   ширину без рекурсии, циклы, тестовый репозиторий (текущий этап).
4. Обратные зависимости.
5. Визуализация: Mermaid, PNG, ASCII-дерево.

## Структура репозитория

```
src/
  main.py               точка входа
  depvis/
    config.py           чтение и проверка INI-конфигурации
    package.py          координаты пакета Maven
    maven.py            загрузка и разбор POM, прямые зависимости
    testrepo.py         тестовый репозиторий из текстового файла
    graph.py            построение графа (BFS) и поиск циклов
    errors.py           ошибки приложения
config.ini              конфигурация по умолчанию
examples/
  jackson.ini           примеры анализа реальных пакетов Maven
  httpclient.ini
  spring_web.ini
  test_*.ini            примеры работы с тестовым репозиторием
  test_repo.txt         описания тестовых репозиториев
  repo_*.txt
  bad_*.ini             примеры ошибок в параметрах
tests/
  test_config.py        тесты конфигурации
  test_package.py       тесты координат пакета
  test_maven.py         тесты разбора POM и прямых зависимостей
  test_testrepo.py      тесты файла тестового репозитория
  test_graph.py         тесты построения графа и поиска циклов
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

Требование вывода параметров относилось только к первому этапу:
при запуске приложение печатало все настраиваемые пользователем
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

## Этап 2. Сбор данных

Приложение само скачивает файл POM пакета по адресу
`{url}/{groupId через /}/{artifactId}/{version}/{artifactId}-{version}.pom`
и разбирает его средствами стандартной библиотеки
(`urllib` и `xml.etree.ElementTree`). Менеджеры пакетов и сторонние
библиотеки не используются.

При определении прямых зависимостей учитываются:

- цепочка родительских POM (`<parent>`) — свойства, унаследованные
  зависимости и `dependencyManagement`;
- подстановка свойств `${...}`, включая `${project.version}`;
- версии из `dependencyManagement`, в том числе импортированные
  из BOM (`<type>pom</type><scope>import</scope>`);
- отбрасываются зависимости областей `test`, `provided`, `system`
  и помеченные `<optional>true</optional>`.

Скачанные POM кэшируются в памяти, повторные обращения к одному
пакету не создают новых запросов.

```
$ python src/main.py
Прямые зависимости пакета org.apache.commons:commons-lang3:3.14.0:
  зависимостей нет
```

```
$ python src/main.py --config examples/jackson.ini
Прямые зависимости пакета com.fasterxml.jackson.core:jackson-databind:2.16.1:
  com.fasterxml.jackson.core:jackson-annotations:2.16.1
  com.fasterxml.jackson.core:jackson-core:2.16.1
```

```
$ python src/main.py --config examples/httpclient.ini
Прямые зависимости пакета org.apache.httpcomponents:httpclient:4.5.14:
  org.apache.httpcomponents:httpcore:4.4.16
  commons-logging:commons-logging:1.2
  commons-codec:commons-codec:1.11
```

У `commons-lang3` все объявленные зависимости имеют область `test`,
поэтому список прямых зависимостей пуст — так же их показывает и
`mvn dependency:tree`.

## Этап 3. Основные операции

Граф зависимостей строится с учётом транзитивности обходом в ширину
(BFS) **без рекурсии**: очередь `collections.deque` и множество уже
посещённых пакетов. Повторный заход в посещённый пакет не выполняется,
поэтому циклические зависимости не приводят к зацикливанию: ребро
остаётся в графе, а сами циклы ищутся отдельно — обходом в глубину
на явном стеке (тоже без рекурсии) — и выводятся списком.

Пакет, зависимости которого получить не удалось (нет в репозитории,
не описан в тестовом файле, не определена версия), попадает в граф
как лист и перечисляется в конце. Недоступность корневого пакета —
ошибка, приложение завершается с кодом 1.

### Тестовый репозиторий

При `test_mode = on` вместо URL используется файл описания графа
репозитория: в строке указан пакет и его прямые зависимости, пакеты
называются большими латинскими буквами, `#` и `;` начинают
комментарий, разделителем может быть пробел или запятая.

Примеры из каталога `examples/`:

| Конфигурация       | Файл              | Случай                               |
| ------------------ | ----------------- | ------------------------------------ |
| `test_mode.ini`    | `test_repo.txt`   | общая зависимость и цикл `A→C→E→A`   |
| `test_tree.ini`    | `repo_tree.txt`   | ромб без циклов                      |
| `test_cycle.ini`   | `repo_cycle.txt`  | цикл `A→B→C→A` и петля `D→D`         |
| `test_single.ini`  | `repo_single.txt` | пакет без зависимостей               |
| `test_missing.ini` | `repo_missing.txt`| зависимость не описана в файле       |
| `test_unknown.ini` | `repo_tree.txt`   | анализируемого пакета нет в файле    |

```
$ python src/main.py --config examples/test_mode.ini
Граф зависимостей пакета A
  пакетов: 5, зависимостей: 6
  A -> B, C
  B -> D
  C -> D, E
  D -> зависимостей нет
  E -> A
Циклические зависимости:
  A -> C -> E -> A
```

```
$ python src/main.py --config examples/test_cycle.ini
Граф зависимостей пакета A
  пакетов: 4, зависимостей: 5
  A -> B, D
  B -> C
  D -> D
  C -> A
Циклические зависимости:
  A -> B -> C -> A
  D -> D
```

```
$ python src/main.py --config examples/test_missing.ini
Граф зависимостей пакета A
  пакетов: 3, зависимостей: 2
  A -> B, C
  B -> зависимостей нет
  C -> зависимостей нет
Не удалось получить зависимости:
  C: пакет C не описан в тестовом репозитории examples\repo_missing.txt
```

```
$ python src/main.py --config examples/test_unknown.ini
Ошибка: пакет Z не описан в тестовом репозитории examples\repo_tree.txt
```

### Реальный репозиторий

```
$ python src/main.py --config examples/spring_web.ini
Граф зависимостей пакета org.springframework:spring-web:6.1.3
  пакетов: 6, зависимостей: 6
  org.springframework:spring-web:6.1.3 -> org.springframework:spring-beans:6.1.3, org.springframework:spring-core:6.1.3, io.micrometer:micrometer-observation:1.12.2
  org.springframework:spring-beans:6.1.3 -> org.springframework:spring-core:6.1.3
  org.springframework:spring-core:6.1.3 -> org.springframework:spring-jcl:6.1.3
  io.micrometer:micrometer-observation:1.12.2 -> io.micrometer:micrometer-commons:1.12.2
  org.springframework:spring-jcl:6.1.3 -> зависимостей нет
  io.micrometer:micrometer-commons:1.12.2 -> зависимостей нет
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

103 теста покрывают разбор конфигурации и POM, свойства и наследование
от родительских POM, фильтрацию областей видимости, тестовый
репозиторий, обход графа, поиск циклов и сообщения об ошибках.
