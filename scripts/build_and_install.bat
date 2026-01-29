@echo off
REM 打包并安装 fast-graph 到本地
REM 使用方法: scripts\build_and_install.bat

echo ==========================================
echo 开始构建 fast-graph 包...
echo ==========================================

REM 清理旧的构建文件
echo 清理旧的构建文件...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"
for /d %%i in (src\*.egg-info) do rmdir /s /q "%%i"

REM 构建包
echo 构建包...
python -m pip install --upgrade build
if errorlevel 1 (
    echo 错误: 安装 build 工具失败
    exit /b 1
)

python -m build
if errorlevel 1 (
    echo 错误: 构建包失败
    exit /b 1
)

REM 安装到本地
echo.
echo ==========================================
echo 安装包到本地...
echo ==========================================

for %%f in (dist\*.whl) do (
    pip install --force-reinstall "%%f"
    if errorlevel 1 (
        echo 错误: 安装包失败
        exit /b 1
    )
)

echo.
echo ==========================================
echo ✅ 安装完成！
echo ==========================================
echo 你可以使用以下命令验证安装：
echo   python -c "import fast_graph; print(fast_graph.__version__)"
echo.

pause
