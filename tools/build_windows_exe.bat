@echo off
rem ============================================================
rem  把图形界面版打包成一个独立的 exe（对方不用装 Python）
rem  必须在 Windows 上运行本脚本；需要联网装一次 pyinstaller
rem  产物在 ..\dist\FirmwareChecksum.exe
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

set PY=
where py >nul 2>nul && set PY=py
if not defined PY (where python >nul 2>nul && set PY=python)
if not defined PY (
  echo 没有找到 Python，请先安装 Python 3。
  pause
  exit /b 1
)

echo 正在安装/更新 pyinstaller ...
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo pyinstaller 安装失败，检查网络后重试。
  pause
  exit /b 1
)

echo 正在打包 ...
%PY% -m PyInstaller --onefile --noconsole --clean ^
  --name FirmwareChecksum ^
  --distpath "%~dp0..\dist" ^
  --workpath "%~dp0..\build" ^
  --specpath "%~dp0..\build" ^
  calcsum_gui.py

if errorlevel 1 (
  echo 打包失败。
  pause
  exit /b 1
)

echo.
echo 打包完成：%~dp0..\dist\FirmwareChecksum.exe
echo 这个 exe 可以直接发给别人，双击就能用，对方不需要装 Python。
echo.
pause
