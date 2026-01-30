# FastGraph

> 为你的 LangGraph 应用快速构建 FastAPI 服务

FastGraph 是一个轻量级工具，让你只需几行代码就能将本地编写的 LangGraph 图转换为完整的 FastAPI 服务，并完美兼容 LangGraph 官方的 `RemoteGraph` 客户端。

## ✨ 核心特性

- 🚀 **一行代码启动服务** - 使用 `fastGraph()` 函数即可创建完整的 API 服务
- 🔌 **完美兼容 RemoteGraph** - 无缝对接 LangGraph 官方客户端
- 🤝 **A2A 协议支持** - 自动启用 Agent-to-Agent 协议，支持 agent 间通信
- 💾 **多种存储方式** - 支持 Memory、Redis + PostgreSQL 方案
- 🌐 **分布式部署** - 支持多实例水平扩展
- 🔄 **流式输出** - 支持实时流式返回执行结果
- 🎯 **状态管理** - 完整的线程状态管理和历史记录
- 🛠️ **人工干预** - 支持 HITL（Human-in-the-Loop）中断和恢复

## 📦 安装

项目暂未发布到 PyPI，需要从源码安装：

```bash
# 1. 克隆仓库
git clone <repository-url>
cd fast-graph

# 2. 使用内置脚本安装
# macOS/Linux
./scripts/build_and_install.sh

# Windows
scripts\build_and_install.bat
```

## 🚀 快速开始

### 1. 创建你的 LangGraph

```python
# my_graph.py
from langgraph.graph import StateGraph, MessagesState, START, END

class MyState(MessagesState):
    content: str

def my_node(state: MyState):
    return {"content": state["content"] + " processed"}

def create_my_graph():
    builder = StateGraph(MyState)
    builder.add_node("my_node", my_node)
    builder.add_edge(START, "my_node")
    builder.add_edge("my_node", END)
    return builder
```

### 2. 启动 FastAPI 服务

```python
# server.py
from fast_graph import fastGraph
from my_graph import create_my_graph

# 一行代码创建服务
app = fastGraph(graphs={
    "my_graph": create_my_graph()
})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. 使用 RemoteGraph 调用

```python
from langgraph.pregel.remote import RemoteGraph

# 连接到远程图
graph = RemoteGraph("my_graph", url="http://localhost:8000")

# 调用图
result = await graph.ainvoke({"content": "hello"})
print(result)  # {"content": "hello processed"}

# 流式调用
async for chunk in graph.astream({"content": "hello"}):
    print(chunk)
```

## ⚙️ 配置存储方式

FastGraph 支持不同存储方式，通过环境变量配置：

### Memory（默认）

无需配置，适合开发和测试：

```bash
# 不设置任何环境变量即使用内存存储
```

**注意：** Memory 模式不支持分布式部署，状态仅存储在单个进程内存中。

### Redis + PostgreSQL

适合生产环境的分布式部署：

```bash
# .env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password
REDIS_DB=0
REDIS_MAX_CONNECTIONS=20
REDIS_KEY_PRE=fast-graph

# .env
POSTGRE_DATABASE_URL=postgresql://user:password@localhost:5432/dbname
POSTGRE_DB_POOL_SIZE=10
POSTGRE_DB_MAX_OVERFLOW=20
POSTGRE_DB_ECHO=false
```

**分布式特性：**
- ✅ 支持多实例水平扩展
- ✅ 持久化存储



## 🤖 A2A 协议支持

FastGraph 自动启用 A2A（Agent-to-Agent）协议，支持 agent 之间的通信和协作。

### A2A 端点

每个注册的 assistant 都会自动暴露以下 A2A 端点：

#### 1. Agent Card 端点

```
GET /.well-known/agent-card.json?assistant_id={assistant_id}
```

返回 agent 的能力描述卡片，包含：
- Agent 名称和描述
- 支持的技能（skills）
- 输入/输出模式
- 能力声明（流式、推送通知等）

**示例：**

```bash
curl "http://localhost:8000/.well-known/agent-card.json?assistant_id=my_graph"
```

#### 2. JSON-RPC 端点

```
POST /a2a/{assistant_id}
```

使用 JSON-RPC 2.0 协议与 agent 交互（暂不支持 tasks/cancel）。

**示例：**

```bash
curl -X POST "http://localhost:8000/a2a/my_graph" \
  -H "Content-Type: application/json" \
  -d '{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/stream",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "Hello from A2A"
        }
      ],
      "messageId": "4865c6da-dada-c7b8-0ae1-ab4d7ed642c0",
      "contextId": "7d7103de-1c62-a2db-c9eb-5c49242f78f9"
    }
  }
}'
```

### A2A 使用场景

#### 场景 1：Agent 间协作

多个 agent 可以通过 A2A 协议相互调用，实现复杂的工作流。


#### 场景 2：跨框架 Agent 通信

不同开发框架下的 agent 可以通过 A2A 协议互相发现和调用。


### A2A 特性

- ✅ **自动启用** - 无需配置，所有 assistant 自动支持 A2A
- ✅ **流式响应** - 支持实时流式返回执行结果
- ✅ **标准协议** - 遵循 A2A 协议规范，兼容其他 A2A agent
- ✅ **多 Agent 支持** - 每个 assistant 都有独立的 A2A 端点
- ⏳ **推送通知** - 暂未启用
- ⏳ **状态历史** - 暂未启用

## 📡 API 接口

FastGraph 提供了完整的 RESTful API，与 LangGraph 官方 API 兼容。

### Assistant（图管理）

#### `GET /assistants/{assistant_id}/graph`
获取图的结构信息，包括节点和边的定义。

**用途：** 查看图的拓扑结构，用于可视化或调试。

**参数：**
- `assistant_id`: 图的 ID
- `xray`: 是否包含子图信息（可选）

### Thread（线程管理）

#### `POST /threads`
创建新的对话线程。

**用途：** 为有状态的对话创建独立的上下文空间。

#### `GET /threads/{thread_id}`
获取线程信息。

**用途：** 查看线程的元数据和配置。

#### `GET /threads/{thread_id}/state`
获取线程的最新状态。

**用途：** 查看当前对话的状态数据，包括所有变量和消息。

#### `POST /threads/{thread_id}/state`
更新线程状态。

**用途：** 手动修改状态，例如在人工干预后更新审批结果。

#### `GET /threads/{thread_id}/state/{checkpoint_id}`
获取指定检查点的状态。

**用途：** 查看历史某个时刻的状态快照。

#### `POST /threads/{thread_id}/state/checkpoint`
通过 POST 请求获取检查点状态。

**用途：** 使用复杂查询条件获取特定检查点。

#### `GET /threads/{thread_id}/history`
获取线程的历史记录。

**用途：** 查看对话的完整执行历史，用于审计或回溯。

**参数：**
- `limit`: 返回记录数量（默认 10）
- `before`: 获取指定检查点之前的历史

#### `POST /threads/{thread_id}/history`
通过 POST 请求获取历史记录。

**用途：** 使用复杂过滤条件查询历史。

### Run（执行管理）

#### `POST /threads/{thread_id}/runs/stream`
在指定线程中执行图并流式返回结果。

**用途：** 有状态执行，支持多轮对话和状态保持。适合聊天机器人、工作流等场景。

**特点：**
- 保存执行状态到线程
- 支持断点续传
- 支持人工干预（HITL）

#### `POST /runs/stream`
无状态执行图并流式返回结果。

**用途：** 一次性执行，不保存状态。适合独立任务、批处理等场景。

**特点：**
- 不需要创建线程
- 每次执行独立
- 性能更高，资源占用更少

## 🎯 使用场景

### 场景 1：有状态对话（使用 Thread）

```python
from langgraph.pregel.remote import RemoteGraph

graph = RemoteGraph("chat_bot", url="http://localhost:8000")

# 创建线程
thread_id = "user_123_session"

# 多轮对话
result1 = await graph.ainvoke(
    {"messages": [{"role": "user", "content": "我叫张三"}]},
    config={"configurable": {"thread_id": thread_id}}
)

result2 = await graph.ainvoke(
    {"messages": [{"role": "user", "content": "我叫什么名字？"}]},
    config={"configurable": {"thread_id": thread_id}}
)
# 机器人会记住之前的对话，回答"张三"
```

### 场景 2：无状态任务（使用 Stateless Run）

```python
# 直接调用，不需要线程
result = await graph.ainvoke({"input": "翻译：Hello World"})
# 每次调用都是独立的，不保存状态
```

### 场景 3：人工干预（HITL）

```python
# 第一次调用，图会在需要审批的地方中断
result = await graph.ainvoke(
    {"content": "需要审批的内容"},
    config={"configurable": {"thread_id": thread_id}}
)

# 检查状态，确认是否在等待
state = await graph.aget_state(
    config={"configurable": {"thread_id": thread_id}}
)

if state.next:  # 有待执行的节点，说明被中断了
    # 人工审批后，更新状态
    await graph.aupdate_state(
        config={"configurable": {"thread_id": thread_id}},
        values={"approval": "APPROVED"}
    )

    # 继续执行
    result = await graph.ainvoke(
        input=None,
        config={"configurable": {"thread_id": thread_id}}
    )
```

### 场景 4：查看执行历史

```python
# 获取线程的所有历史状态
async for state in graph.aget_state_history(
    config={"configurable": {"thread_id": thread_id}}
):
    print(f"Checkpoint: {state.config['configurable']['checkpoint_id']}")
    print(f"State: {state.values}")
```

## 🎨 设计亮点

### 1. 零侵入集成

无需修改现有的 LangGraph 代码，只需将图注册到 FastGraph 即可：

```python
# 你的图代码完全不需要改动
app = fastGraph(graphs={"my_graph": my_existing_graph})
```

### 2. 完美兼容 RemoteGraph

FastGraph 实现了 LangGraph 官方的 API 规范，可以无缝使用 `RemoteGraph` 客户端：

```python
# 使用官方客户端，享受完整的类型提示和功能
from langgraph.pregel.remote import RemoteGraph
graph = RemoteGraph("my_graph", url="http://localhost:8000")
```

### 3. 灵活的存储策略

根据场景选择合适的存储：
- **Memory**: 开发测试，零配置
- **Redis + PostgreSQL**: 生产环境，分布式和持久化，高并发、高吞吐、高可用

### 4. 流式输出

支持实时流式返回执行结果，提升用户体验：

```python
async for chunk in graph.astream(input_data):
    print(chunk)  # 实时显示每个节点的输出
```

### 5. 状态管理

完整的状态生命周期管理：
- 创建和查询线程
- 获取当前状态和历史状态
- 手动更新状态
- 支持检查点和回溯

### 6. 自定义生命周期

支持自定义应用启动和关闭逻辑：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def custom_lifespan(app):
    # 启动时的初始化
    print("应用启动")
    await init_external_services()

    yield

    # 关闭时的清理
    await cleanup_resources()
    print("应用关闭")

app = fastGraph(
    graphs={"my_graph": my_graph},
    custom_lifespan=custom_lifespan
)
```

## 🌐 分布式部署

FastGraph 支持水平扩展，可以部署多个实例来提高吞吐量和可用性。

### 部署架构

```
                    ┌─────────────┐
                    │   Nginx /   │
                    │ Load Balancer│
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │ FastGraph │    │ FastGraph │    │ FastGraph │
    │ Instance 1│    │ Instance 2│    │ Instance 3│
    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
            ┌─────▼─────┐    ┌──────▼──────┐
            │   Redis   │    │ PostgreSQL  │
            │  (Queue)  │    │   (State)   │
            └───────────┘    └─────────────┘
```

### 配置示例

#### 使用 Redis + PostgreSQL（生产环境推荐）

这是一套完整的生产方案：
- **Redis**：作为消息队列，负责事件的处理
- **PostgreSQL**：作为状态存储，负责持久化线程状态和历史记录

```bash
# .env - 所有实例使用相同配置

# Redis 配置（消息队列）
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
REDIS_MAX_CONNECTIONS=20
REDIS_KEY_PRE=fast-graph

# PostgreSQL 配置（状态存储）
POSTGRE_DATABASE_URL=postgresql://user:password@postgres.example.com:5432/fastgraph
POSTGRE_DB_POOL_SIZE=10
POSTGRE_DB_MAX_OVERFLOW=20
POSTGRE_DB_ECHO=false
```

#### 启动多个实例

```bash
# 实例 1 - 端口 8000
uvicorn server:app --host 0.0.0.0 --port 8000

# 实例 2 - 端口 8001
uvicorn server:app --host 0.0.0.0 --port 8001

# 实例 3 - 端口 8002
uvicorn server:app --host 0.0.0.0 --port 8002
```

所有实例共享同一套 Redis（消息队列）和 PostgreSQL（状态存储），实现真正的分布式部署。

#### 配置负载均衡（Nginx）

```nginx
upstream fastgraph_backend {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://fastgraph_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Docker Compose 部署

完整的容器化部署方案，包含 Redis（消息队列）、PostgreSQL（状态存储）和多个 FastGraph 实例：

```yaml
version: '3.8'

services:
  # Redis - 消息队列
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --requirepass your_password
    volumes:
      - redis_data:/data

  # PostgreSQL - 状态存储
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: fastgraph
      POSTGRES_USER: fastgraph
      POSTGRES_PASSWORD: your_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # FastGraph 服务（多实例）
  fastgraph:
    build: .
    environment:
      # Redis 配置
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD: your_password
      REDIS_DB: 0
      REDIS_MAX_CONNECTIONS: 20
      REDIS_KEY_PRE: fast-graph
      # PostgreSQL 配置
      POSTGRE_DATABASE_URL: postgresql://fastgraph:your_password@postgres:5432/fastgraph
      POSTGRE_DB_POOL_SIZE: 10
      POSTGRE_DB_MAX_OVERFLOW: 20
    ports:
      - "8000-8002:8000"
    depends_on:
      - redis
      - postgres
    deploy:
      replicas: 3  # 部署 3 个实例

  # Nginx 负载均衡
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - fastgraph

volumes:
  redis_data:
  postgres_data:
```

### 性能优化建议

1. **连接池配置**
   ```bash
   # 根据实例数量和并发量调整
   POSTGRE_DB_POOL_SIZE=20        # 每个实例的数据库连接池大小
   POSTGRE_DB_MAX_OVERFLOW=20     # 连接池溢出大小
   REDIS_MAX_CONNECTIONS=30       # 每个实例的 Redis 连接数
   ```

2. **实例数量规划**
   - CPU 密集型任务：实例数 = CPU 核心数
   - I/O 密集型任务：实例数 = CPU 核心数 × 2
   - 建议从 2-3 个实例开始，根据负载逐步扩展

3. **监控指标**
   - 请求响应时间和吞吐量
   - Redis 队列长度和消息处理速度
   - PostgreSQL 连接数和查询性能
   - Redis 内存使用率
   - 各实例的 CPU 和内存使用

4. **高可用建议**
   - Redis 使用主从复制或 Redis Cluster
   - PostgreSQL 配置主从复制或使用云数据库
   - FastGraph 实例至少部署 3 个以上
   - 配置健康检查和自动重启

## 📚 更多示例

查看 `graph_demo/` 目录获取完整示例：
- `graph_demo/graph.py` - 各种图的实现示例
- `graph_demo/state.py` - 状态定义示例
- `server.py` - 服务启动示例
- `tests/test_remote_graph.py` - RemoteGraph 使用示例

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
