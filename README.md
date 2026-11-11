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
   ширину без рекурсии, циклы, тестовый репозиторий.
4. **Дополнительные операции** — обратные зависимости.
5. **Визуализация** — Mermaid, изображение PNG, ASCII-дерево
   (текущий этап).

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
    mermaid.py          описание графа на языке Mermaid
    tree.py             вывод зависимостей ASCII-деревом
    image.py            размещение узлов и рисование графа
    png.py              растровый холст и запись файла PNG
    font.py             растровый шрифт 5x7 для подписей
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
  *.mmd                 описания Mermaid, построенные по примерам
tests/
  test_config.py        тесты конфигурации
  test_package.py       тесты координат пакета
  test_maven.py         тесты разбора POM и прямых зависимостей
  test_testrepo.py      тесты файла тестового репозитория
  test_graph.py         тесты построения графа и поиска циклов
  test_visual.py        тесты Mermaid, ASCII-дерева и PNG
  test_main.py          тесты точки входа
run.sh / run.bat        запуск приложения
pytest.ini              настройки pytest (путь к пакету src)
compare/                сравнение с mvn dependency:tree
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

## Этап 4. Обратные зависимости

Режим требовался только на этапе 4, поэтому на этапе 5 он убран
вместе с параметром `output.reverse` и примерами `reverse_*.ini`.
Ниже описано, как он работал.

При `reverse = on` приложение выводит обратные зависимости пакета —
те пакеты, которые зависят от него (прямо или через цепочку). Для
этого прямые связи репозитория переворачиваются, а дальше работает
**тот же обход в ширину**, что и на этапе 3: `build_graph` получает
вместо репозитория объект `ReverseView` с тем же методом
`dependencies`. Поэтому циклы обрабатываются так же.

Обратные зависимости строятся для тестового репозитория: в нём
известны все пакеты. Репозиторий Maven такой возможности не даёт —
узнать, кто зависит от пакета, без полного индекса всех пакетов
(то есть без менеджера пакетов) нельзя, поэтому в этом режиме
выводится ошибка.

| Конфигурация       | Репозиторий       | Случай                           |
| ------------------ | ----------------- | -------------------------------- |
| `reverse_d.ini`    | `repo_tree.txt`   | общий потомок, два пути наверх    |
| `reverse_e.ini`    | `test_repo.txt`   | обратные зависимости внутри цикла |
| `reverse_a.ini`    | `repo_cycle.txt`  | цикл целиком                      |
| `reverse_b.ini`    | `repo_missing.txt`| единственная обратная зависимость |
| `reverse_maven.ini`| Maven             | режим недоступен, ошибка          |

```
$ python src/main.py --config examples/reverse_d.ini
Обратные зависимости пакета D
  пакетов: 3
  D <- B, C
  B <- A
  C <- A
  A <- от него никто не зависит
```

```
$ python src/main.py --config examples/reverse_e.ini
Обратные зависимости пакета E
  пакетов: 2
  E <- C
  C <- A
  A <- E
Циклические зависимости:
  E <- C <- A <- E
```

```
$ python src/main.py --config examples/reverse_maven.ini
Ошибка: обратные зависимости доступны только для тестового
репозитория: репозиторий Maven не позволяет узнать, кто зависит
от пакета, без полного индекса всех пакетов
```

## Этап 5. Визуализация

Для построенного графа приложение:

1. формирует текстовое представление на языке диаграмм **Mermaid**
   и печатает его на экран, одновременно сохраняя рядом с картинкой
   файл с расширением `.mmd`;
2. сохраняет изображение графа в файле **PNG** (имя задаётся
   параметром `output.image`);
3. при `ascii_tree = on` печатает зависимости в виде
   **ASCII-дерева**.

Изображение рисуется самостоятельно: узлы раскладываются по уровням
обхода в ширину, рёбра рисуются алгоритмом Брезенхэма, подписи —
растровым шрифтом 5x7 (`font.py`), файл PNG собирается из блоков
IHDR/IDAT/IEND со сжатием `zlib` (`png.py`). Сторонние графические
библиотеки не используются, поэтому подписи выводятся латиницей
заглавными буквами. Корневой пакет выделен оранжевой рамкой, рёбра
циклов — красным, пакеты с неизвестными зависимостями — серой рамкой.

### Три примера

| Пакет                                                | Конфигурация              |
| ---------------------------------------------------- | ------------------------- |
| `com.fasterxml.jackson.core:jackson-databind:2.16.1` | `examples/jackson.ini`    |
| `org.apache.httpcomponents:httpclient:4.5.14`        | `examples/httpclient.ini` |
| `org.springframework:spring-web:6.1.3`               | `examples/spring_web.ini` |

Изображения в репозитории не хранятся: бинарные файлы в нём
запрещены. Они создаются при запуске — например,
`examples/spring_web.png` после команды
`python src/main.py --config examples/spring_web.ini`. Описания
Mermaid тех же графов лежат рядом в текстовых файлах
`examples/*.mmd`; их можно открыть в любом редакторе Mermaid
(например, mermaid.live) и получить ту же картинку.

Пример с циклом — тестовый репозиторий `examples/test_mode.ini`
(изображение `examples/A.png`, описание `examples/A.mmd`).

```
$ python src/main.py --config examples/spring_web.ini
...
Представление графа на языке Mermaid:
  graph TD
      n0["org.springframework:spring-web:6.1.3"]
      n1["org.springframework:spring-beans:6.1.3"]
      n2["org.springframework:spring-core:6.1.3"]
      n3["io.micrometer:micrometer-observation:1.12.2"]
      n4["org.springframework:spring-jcl:6.1.3"]
      n5["io.micrometer:micrometer-commons:1.12.2"]
      n0 --> n1
      n0 --> n2
      n0 --> n3
      n1 --> n2
      n2 --> n4
      n3 --> n5
      classDef root fill:#fff6e6,stroke:#c86e1e,stroke-width:2px;
      classDef unresolved fill:#f4f4f4,stroke:#999,stroke-dasharray:4;
      class n0 root;
Изображение графа: examples\spring_web.png
Описание Mermaid: examples\spring_web.mmd
Дерево зависимостей:
  org.springframework:spring-web:6.1.3
  ├── org.springframework:spring-beans:6.1.3
  │   └── org.springframework:spring-core:6.1.3
  │       └── org.springframework:spring-jcl:6.1.3
  ├── org.springframework:spring-core:6.1.3 (повтор)
  └── io.micrometer:micrometer-observation:1.12.2
      └── io.micrometer:micrometer-commons:1.12.2
```

В ASCII-дереве уже раскрытый пакет помечается как `(повтор)`,
а возврат к пакету из текущей ветви — как `(цикл)`; дерево строится
без рекурсии, на явном стеке:

```
$ python src/main.py --config examples/test_cycle.ini
...
Дерево зависимостей:
  A
  ├── B
  │   └── C
  │       └── A (цикл)
  └── D
      └── D (цикл)
```

### Сравнение со штатным инструментом

Штатное средство Maven — `mvn dependency:tree` (Apache Maven 3.9.9,
JDK 21, плагин `maven-dependency-plugin` 3.8.1). Для каждого из трёх
пакетов в каталоге `compare/` лежит минимальный проект `pom.xml`
с этим пакетом в качестве единственной зависимости и сохранённый
вывод Maven (`mvn_tree.txt`). Повторить сравнение можно командой
`compare/run.sh` или `compare\run.bat` (нужны JDK и Maven в `PATH`).

Вывод `mvn dependency:tree` (первая строка — служебный проект):

```
demo:demo-jackson:jar:1.0
\- com.fasterxml.jackson.core:jackson-databind:jar:2.16.1:compile
   +- com.fasterxml.jackson.core:jackson-annotations:jar:2.16.1:compile
   \- com.fasterxml.jackson.core:jackson-core:jar:2.16.1:compile

demo:demo-httpclient:jar:1.0
\- org.apache.httpcomponents:httpclient:jar:4.5.14:compile
   +- org.apache.httpcomponents:httpcore:jar:4.4.16:compile
   +- commons-logging:commons-logging:jar:1.2:compile
   \- commons-codec:commons-codec:jar:1.11:compile

demo:demo-spring_web:jar:1.0
\- org.springframework:spring-web:jar:6.1.3:compile
   +- org.springframework:spring-beans:jar:6.1.3:compile
   +- org.springframework:spring-core:jar:6.1.3:compile
   |  \- org.springframework:spring-jcl:jar:6.1.3:compile
   \- io.micrometer:micrometer-observation:jar:1.12.2:compile
      \- io.micrometer:micrometer-commons:jar:1.12.2:compile
```

Во всех трёх случаях состав пакетов и версии совпадают с графом,
который строит инструмент. Различия в представлении и поведении:

1. **Где раскрывается общий пакет.** В подробном режиме
   (`-Dverbose`, файл `compare/spring_web/mvn_tree_verbose.txt`)
   Maven показывает, что `spring-core` встречается дважды: прямо у
   `spring-web` и через `spring-beans`. Раскрывает он ближайшее к
   корню вхождение, а второе помечает
   `omitted for duplicate`:

   ```
   +- org.springframework:spring-beans:jar:6.1.3:compile
   |  \- (org.springframework:spring-core:jar:6.1.3:compile - omitted for duplicate)
   +- org.springframework:spring-core:jar:6.1.3:compile
   |  \- org.springframework:spring-jcl:jar:6.1.3:compile
   ```

   Инструмент строит граф: `spring-core` — один узел с двумя
   входящими рёбрами. В ASCII-дереве он раскрыт там, где его первым
   встречает обход в глубину (под `spring-beans`), а прямое вхождение
   помечено `(повтор)`. Состав дерева тот же, отличается только
   место раскрытия.
2. **Разрешение конфликтов версий.** Maven применяет правило
   «ближайшая версия побеждает» и печатает `omitted for conflict`.
   Инструмент версию не выбирает: разные версии одного артефакта
   остаются разными узлами графа. В выбранных примерах конфликтов
   нет, поэтому результаты совпадают.
3. **Исключения.** `<exclusions>` в POM инструментом не учитываются,
   Maven вырезает исключённые ветви. В примерах исключений нет.
4. **Области видимости.** Для собственного проекта
   `mvn dependency:tree` показывает и `test`/`provided`-зависимости.
   Инструмент обходит только `compile` и `runtime` — те, что
   переходят к потребителю пакета. Транзитивно Maven поступает так
   же, поэтому у пакета-зависимости результаты совпадают. У
   `commons-lang3` все зависимости тестовые, и инструмент показывает
   пустой список.
5. **Циклы.** В реальных репозиториях Maven циклов обычно нет. Они
   показаны на тестовом репозитории, к которому Maven неприменим.

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

117 тестов покрывают разбор конфигурации и POM, свойства и
наследование от родительских POM, фильтрацию областей видимости,
тестовый репозиторий, обход графа, поиск циклов, Mermaid,
ASCII-дерево, запись PNG и сообщения об ошибках. Путь к пакету
`src` задаёт `pytest.ini`.
