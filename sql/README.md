# 数据库表结构说明

本目录包含 FastGraph 所需的 PostgreSQL 数据库表结构定义。

## 自动建表 vs 手动建表

### 自动建表（默认）

FastGraph 默认在启动时自动创建所需的数据库表。这适合开发和测试环境。

```bash
# .env 配置（默认行为）
POSTGRE_AUTO_CREATE_TABLES=true
```

### 手动建表（生产环境推荐）

在生产环境中，出于安全和权限管理考虑，通常不允许应用自动创建表。你可以：

```bash
# .env 配置
POSTGRE_AUTO_CREATE_TABLES=false
```

然后使用 init.sql 中的 sql 进行手动建表。
