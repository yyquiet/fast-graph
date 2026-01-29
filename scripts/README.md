# 构建和安装脚本

这个目录包含了用于构建和安装 fast-graph 包的脚本。

## 脚本说明

### 1. 构建并安装到本地

**Linux/macOS:**
```bash
./scripts/build_and_install.sh
```

**Windows:**
```cmd
scripts\build_and_install.bat
```

这个脚本会：
- 清理旧的构建文件
- 构建 wheel 包
- 自动安装到当前 Python 环境

### 2. 仅构建（不安装）

**Linux/macOS:**
```bash
./scripts/build.sh
```

**Windows:**
```cmd
scripts\build.bat
```

这个脚本会：
- 清理旧的构建文件
- 构建 wheel 和 tar.gz 包
- 生成的文件位于 `dist/` 目录

### 3. 清理构建文件

**Linux/macOS:**
```bash
./scripts/clean.sh
```

**Windows:**
```cmd
scripts\clean.bat
```

这个脚本会清理：
- `dist/` 目录
- `build/` 目录
- `*.egg-info` 目录
- `__pycache__` 目录
- `.pyc` 和 `.pyo` 文件

## 使用示例

### 开发流程

1. **修改代码后重新构建并安装：**
   ```bash
   ./scripts/build_and_install.sh
   ```

2. **验证安装：**
   ```bash
   python -c "import fast_graph; print(fast_graph.__version__)"
   ```

3. **测试包：**
   ```bash
   pytest
   ```

### 发布流程

1. **清理旧文件：**
   ```bash
   ./scripts/clean.sh
   ```

2. **构建包：**
   ```bash
   ./scripts/build.sh
   ```

3. **检查生成的文件：**
   ```bash
   ls -lh dist/
   ```

4. **上传到 PyPI（可选）：**
   ```bash
   python -m pip install --upgrade twine
   python -m twine upload dist/*
   ```

## 注意事项

- 确保已安装 Python 3.12 或更高版本
- 建议在虚拟环境中运行这些脚本
- Windows 用户需要在 PowerShell 或 CMD 中运行 `.bat` 脚本
- Linux/macOS 用户需要给 `.sh` 脚本添加执行权限（已自动添加）

## 依赖

这些脚本需要以下工具：
- `build` - Python 构建工具（脚本会自动安装）
- `pip` - Python 包管理器（通常已预装）

## 故障排除

### 权限错误（Linux/macOS）

如果遇到权限错误，运行：
```bash
chmod +x scripts/*.sh
```

### 构建失败

1. 确保 `pyproject.toml` 配置正确
2. 检查是否有语法错误
3. 尝试先清理再构建：
   ```bash
   ./scripts/clean.sh && ./scripts/build.sh
   ```

### 安装失败

1. 确保虚拟环境已激活
2. 尝试升级 pip：
   ```bash
   python -m pip install --upgrade pip
   ```
3. 使用 `--force-reinstall` 强制重新安装
