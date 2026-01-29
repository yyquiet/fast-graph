@echo off
REM 仅构建 fast-graph 包（不安装）
REM 使用方法: scripts\build.bat

echo ==========================================
echo 开始构建 fast-graph 包...
echo ==========================================

REM 清理旧的构建文件
echo 清理旧的构建文件...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"
for /d %%i in (src\*.egg-info) do rmdir /s /q "%%i"

REM 确保安装了 build 工具
echo 检查构建工具...
python -m pip install --upgrade build
if errorlevel 1 (
    echo 错误: 安装 build 工具失败
    exit /b 1
)

REM 构建包
echo 构建包...
python -m build
if errorlevel 1 (
    echo 错误: 构建包失败
    exit /b 1
)

echo.
echo ==========================================
echo ✅ 构建完成！
echo ==========================================
echo 生成的文件位于 dist\ 目录：
dir /b dist\
echo.
echo 你可以使用以下命令安装：
echo   pip install dist\*.whl
echo.

pause
