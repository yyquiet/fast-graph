#!/bin/bash

# 仅构建 fast-graph 包（不安装）
# 使用方法: ./scripts/build.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "开始构建 fast-graph 包..."
echo "=========================================="

# 清理旧的构建文件
echo "清理旧的构建文件..."
rm -rf dist/ build/ *.egg-info src/*.egg-info

# 检测包管理器并安装 build 工具
echo "检查构建工具..."
if command -v uv &> /dev/null; then
    echo "检测到 uv，使用 uv 安装构建工具..."
    uv pip install --upgrade build
elif command -v pip &> /dev/null; then
    echo "使用 pip 安装构建工具..."
    pip install --upgrade build
else
    echo "使用 python -m pip 安装构建工具..."
    python -m pip install --upgrade build
fi

# 构建包
echo "构建包..."
python -m build

echo ""
echo "=========================================="
echo "✅ 构建完成！"
echo "=========================================="
echo "生成的文件位于 dist/ 目录："
ls -lh dist/
echo ""
echo "你可以使用以下命令安装："
echo "  pip install dist/*.whl"
echo ""
