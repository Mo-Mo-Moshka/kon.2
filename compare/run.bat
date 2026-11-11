@echo off
rem Dependency tree built by the standard Maven tool.
rem Requires JDK and Maven (the mvn command in PATH).
for %%n in (jackson httpclient spring_web) do (
    echo == %%n
    pushd "%~dp0%%n"
    call mvn -q -B org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree -DoutputFile=mvn_tree.txt
    type mvn_tree.txt
    popd
)
