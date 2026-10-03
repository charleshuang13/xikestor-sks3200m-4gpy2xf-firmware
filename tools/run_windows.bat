@echo off
rem ============================================================
rem  双击本文件即可打开「固件校验和工具」图形界面
rem  需要电脑上装了 Python 3（python.org 下载安装即可，勾选 Add to PATH）
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

set PY=
where pyw >nul 2>nul && set PY=pyw
if not defined PY (where pythonw >nul 2>nul && set PY=pythonw)
if not defined PY (where py >nul 2>nul && set PY=py)
if not defined PY (where python >nul 2>nul && set PY=python)

if not defined PY (
  echo.
  echo 没有找到 Python。请先安装 Python 3：https://www.python.org/downloads/
  echo 安装时记得勾选 "Add python.exe to PATH"。
  echo.
  pause
  exit /b 1
)

start "" %PY% "%~dp0calcsum_gui.py"
