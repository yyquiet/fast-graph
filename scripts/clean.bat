@echo off
REM 清理构建文件
REM 使用方法: scripts\clean.bat

echo 清理构建文件...

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"
for /d %%i in (src\*.egg-info) do rmdir /s /q "%%i"
if exist .pytest_cache rmdir /s /q .pytest_cache

REM 清理 __pycache__ 目录
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"

REM 清理 .pyc 和 .pyo 文件
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul

echo ✅ 清理完成！
pause
