#!/bin/sh
# Получить дерево зависимостей штатным инструментом Maven.
# Нужны установленные JDK и Maven (команда mvn в PATH).
set -e
cd "$(dirname "$0")"
for name in jackson httpclient spring_web; do
    echo "== $name"
    (cd "$name" && mvn -q -B \
        org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree \
        -DoutputFile=mvn_tree.txt && cat mvn_tree.txt)
done
