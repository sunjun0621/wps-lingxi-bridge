@echo off
rem test stub wrapper: LINGXI_BRIDGE_EXE must be a directly executable file
rem (ASCII only: cmd reads bat with codepage 936, UTF-8 Chinese comments break it)
python "%~dp0fake_lingxi.py" %*
