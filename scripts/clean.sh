#!/bin/bash

# 清理构建文件
# 使用方法: ./scripts/clean.sh

echo "清理构建文件..."

rm -rf dist/
rm -rf build/
rm -rf *.egg-info
rm -rf src/*.egg-info
rm -rf .pytest_cache/
rm -rf __pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

echo "✅ 清理完成！"
