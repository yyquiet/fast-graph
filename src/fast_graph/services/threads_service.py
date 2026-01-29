from typing import List, Optional, Dict, Any
import threading

from ..models import (
    Thread,
    ThreadCreate,
    ThreadSearchRequest,
    ThreadState,
    ThreadStateUpdate,
    ThreadStateUpdateResponse,
    ThreadStateCheckpointRequest,
    ThreadStateSearch,
    Task,
    CheckpointConfig,
)
from ..global_config import GlobalConfig
from ..graph.registry import get_graph
from ..graph.executor import GraphExecutor
from ..errors import ResourceNotFoundError, GraphNotFoundError
from .assistants_service import AssistantsService


class ThreadsService:
    """线程安全的单例 Service"""

    _instance: Optional['ThreadsService'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式：确保只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 threads（只执行一次）"""
        self.executor = GraphExecutor(GlobalConfig.global_threads_manager)
        self.assistants_service = AssistantsService()

    async def create_thread(self, request: ThreadCreate) -> Thread:
        """Create a thread."""
        return await GlobalConfig.global_threads_manager.create(
            thread_id=request.thread_id,
            metadata=request.metadata,
            if_exists=request.if_exists,
        )


    async def search(self, request: ThreadSearchRequest) -> List[Thread]:
        """Search for threads."""
        limit = request.limit if request.limit else 10
        offset = request.offset if request.offset else 0
        return await GlobalConfig.global_threads_manager.search(
            ids=request.ids,
            metadata=request.metadata,
            status=request.status,
            limit=limit,
            offset=offset,
        )

    async def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        return await GlobalConfig.global_threads_manager.get(thread_id)

    async def _get_graph_for_thread(self, thread_id: str):
        """获取线程关联的图"""
        # 从线程的 metadata 中获取 assistant_id
        thread = await self.get(thread_id)
        if not thread:
            raise ResourceNotFoundError(f"Thread {thread_id} not found")

        assistant_id = thread.metadata.get("assistant_id")
        if not assistant_id:
            raise ResourceNotFoundError(f"Thread {thread_id} has no associated assistant")

        # 获取图
        assistant = await self.assistants_service.get_by_id(assistant_id)
        if assistant is None:
            raise GraphNotFoundError(
                f"Graph not found for assistant_id: {assistant_id}"
            )
        graph = await get_graph(assistant.graph_id)
        if graph is None:
            raise GraphNotFoundError(
                f"Graph not found for assistant_id: {assistant_id}"
            )

        # 配置 checkpointer
        graph.checkpointer = GlobalConfig.global_checkpointer_manager.get_checkpointer()

        return graph

    def _convert_state_snapshot_to_thread_state(self, snapshot: Any) -> ThreadState:
        """将 LangGraph 的 StateSnapshot 转换为 ThreadState 模型"""
        # 提取 checkpoint 信息
        checkpoint_config = CheckpointConfig(
            thread_id=snapshot.config.get("configurable", {}).get("thread_id") if hasattr(snapshot, 'config') else None,
            checkpoint_id=snapshot.config.get("configurable", {}).get("checkpoint_id") if hasattr(snapshot, 'config') else None,
            checkpoint_ns=snapshot.config.get("configurable", {}).get("checkpoint_ns") if hasattr(snapshot, 'config') else None,
            checkpoint_map=None,
        )

        # 提取 tasks
        tasks = None
        if hasattr(snapshot, 'tasks') and snapshot.tasks:
            from ..models import Interrupt
            tasks = []
            for task in snapshot.tasks:
                # 转换 task.interrupts
                task_interrupts = None
                if hasattr(task, 'interrupts') and task.interrupts:
                    task_interrupts = []
                    for interrupt in task.interrupts:
                        # 如果是 LangGraph 的 Interrupt 对象，转换为我们的模型
                        if hasattr(interrupt, 'value'):
                            task_interrupts.append(Interrupt(
                                id=getattr(interrupt, 'id', None),
                                value=getattr(interrupt, 'value', {})
                            ))
                        elif isinstance(interrupt, dict):
                            task_interrupts.append(Interrupt(
                                id=interrupt.get('id'),
                                value=interrupt.get('value', {})
                            ))
                        else:
                            # 已经是我们的 Interrupt 模型
                            task_interrupts.append(interrupt)

                tasks.append(Task(
                    id=task.id,
                    name=task.name,
                    error=task.error if hasattr(task, 'error') else None,
                    interrupts=task_interrupts,
                    checkpoint=CheckpointConfig(
                        thread_id=task.checkpoint.get("configurable", {}).get("thread_id") if hasattr(task, 'checkpoint') and task.checkpoint else None,
                        checkpoint_id=task.checkpoint.get("configurable", {}).get("checkpoint_id") if hasattr(task, 'checkpoint') and task.checkpoint else None,
                        checkpoint_ns=task.checkpoint.get("configurable", {}).get("checkpoint_ns") if hasattr(task, 'checkpoint') and task.checkpoint else None,
                        checkpoint_map=None,
                    ) if hasattr(task, 'checkpoint') and task.checkpoint else None,
                    state=None,  # 避免递归
                ))

        # 提取 parent_checkpoint
        parent_checkpoint = None
        if hasattr(snapshot, 'parent_config') and snapshot.parent_config:
            parent_checkpoint = snapshot.parent_config.get("configurable", {})

        # 提取 interrupts
        interrupts = None
        if hasattr(snapshot, 'interrupts') and snapshot.interrupts:
            from ..models import Interrupt
            interrupts = [
                Interrupt(
                    id=interrupt.get("id") if isinstance(interrupt, dict) else getattr(interrupt, 'id', None),
                    value=interrupt.get("value", {}) if isinstance(interrupt, dict) else (getattr(interrupt, 'value', None) or {})
                )
                for interrupt in snapshot.interrupts
            ]

        return ThreadState(
            values=snapshot.values,
            next=list(snapshot.next) if snapshot.next else [],
            tasks=tasks,
            checkpoint=checkpoint_config,
            metadata=snapshot.metadata if hasattr(snapshot, 'metadata') else {},
            created_at=snapshot.created_at if hasattr(snapshot, 'created_at') else "",
            parent_checkpoint=parent_checkpoint,
            interrupts=interrupts,
        )

    async def get_latest_state(
        self,
        thread_id: str,
        subgraphs: Optional[bool] = None
    ) -> ThreadState:
        """获取线程的最新状态"""
        graph = await self._get_graph_for_thread(thread_id)

        # 获取状态
        snapshot = await self.executor.get_state(
            graph,
            thread_id,
            subgraphs=subgraphs or False
        )

        return self._convert_state_snapshot_to_thread_state(snapshot)

    async def get_state_at_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        subgraphs: Optional[bool] = None
    ) -> ThreadState:
        """获取线程在特定 checkpoint 的状态"""
        graph = await self._get_graph_for_thread(thread_id)

        # 获取状态
        snapshot = await self.executor.get_state(
            graph,
            thread_id,
            checkpoint_id=checkpoint_id,
            subgraphs=subgraphs or False
        )

        return self._convert_state_snapshot_to_thread_state(snapshot)

    async def get_state_at_checkpoint_post(
        self,
        thread_id: str,
        request: ThreadStateCheckpointRequest,
        subgraphs: Optional[bool] = None
    ) -> ThreadState:
        """获取线程在特定 checkpoint 的状态（POST 方法）"""
        graph = await self._get_graph_for_thread(thread_id)

        # 使用 request 中的 subgraphs 或查询参数中的 subgraphs
        use_subgraphs = request.subgraphs if request.subgraphs is not None else (subgraphs or False)

        # 获取状态
        snapshot = await self.executor.get_state(
            graph,
            thread_id,
            checkpoint_id=request.checkpoint.checkpoint_id,
            checkpoint_ns=request.checkpoint.checkpoint_ns,
            subgraphs=use_subgraphs
        )

        return self._convert_state_snapshot_to_thread_state(snapshot)

    async def get_history(
        self,
        thread_id: str,
        limit: int = 10,
        before: Optional[str] = None
    ) -> List[ThreadState]:
        """获取线程的历史状态"""
        graph = await self._get_graph_for_thread(thread_id)

        # 构建 before 配置
        before_config = None
        if before:
            before_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": before
                }
            }

        # 获取历史（异步迭代器）
        history_iterator = await self.executor.get_state_history(
            graph,
            thread_id,
            before=before_config,
            limit=limit
        )

        # 转换为 ThreadState 列表（异步迭代）
        result = []
        async for snapshot in history_iterator:
            result.append(self._convert_state_snapshot_to_thread_state(snapshot))
        return result

    async def get_history_post(
        self,
        thread_id: str,
        request: ThreadStateSearch
    ) -> List[ThreadState]:
        """获取线程的历史状态（POST 方法）"""
        graph = await self._get_graph_for_thread(thread_id)

        # 构建 before 配置
        before_config = None
        if request.before:
            before_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": request.before.checkpoint_id,
                }
            }
            if request.before.checkpoint_ns:
                before_config["configurable"]["checkpoint_ns"] = request.before.checkpoint_ns

        # 获取历史（异步迭代器）
        history_iterator = await self.executor.get_state_history(
            graph,
            thread_id,
            checkpoint_ns=request.checkpoint.checkpoint_ns if request.checkpoint else None,
            filter=request.metadata,
            before=before_config,
            limit=request.limit or 10
        )

        # 转换为 ThreadState 列表（异步迭代）
        result = []
        async for snapshot in history_iterator:
            result.append(self._convert_state_snapshot_to_thread_state(snapshot))
        return result

    async def update_state(
        self,
        thread_id: str,
        request: ThreadStateUpdate
    ) -> ThreadStateUpdateResponse:
        """更新线程状态"""
        graph = await self._get_graph_for_thread(thread_id)

        # 构建配置
        config: Dict[str, Any] = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # 添加 checkpoint 配置
        if request.checkpoint:
            if request.checkpoint.checkpoint_id:
                config["configurable"]["checkpoint_id"] = request.checkpoint.checkpoint_id
            if request.checkpoint.checkpoint_ns:
                config["configurable"]["checkpoint_ns"] = request.checkpoint.checkpoint_ns

        # 更新状态
        updated_config = await graph.aupdate_state(
            config,  # type: ignore
            request.values,
            as_node=request.as_node
        )

        # 返回更新后的 checkpoint
        configurable = updated_config.get("configurable", {}) if isinstance(updated_config, dict) else {}
        return ThreadStateUpdateResponse(
            checkpoint=CheckpointConfig(
                thread_id=configurable.get("thread_id"),
                checkpoint_id=configurable.get("checkpoint_id"),
                checkpoint_ns=configurable.get("checkpoint_ns"),
                checkpoint_map=None,
            )
        )

