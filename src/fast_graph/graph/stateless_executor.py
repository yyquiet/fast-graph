"""
LangGraph 无状态执行器
"""

from typing import Any, Dict, List, Union
from langgraph.graph.state import CompiledStateGraph

from ..managers import (
    BaseStreamQueue,
    EventMessage,
)
from ..models import RunCreateStateless, StreamMode


class StatelessGraphExecutor:
    """
    LangGraph 无状态图执行器

    负责执行 LangGraph 图并将事件流式传输到队列中。
    不保存状态，每次执行都是独立的。
    """

    def __init__(self):
        """
        初始化无状态图执行器
        """

    async def stream_graph(
        self,
        graph: CompiledStateGraph,
        payload: RunCreateStateless,
        queue: BaseStreamQueue,
    ) -> None:
        """
        执行图并流式传输事件

        Args:
            graph: 要执行的 LangGraph 编译图
            payload: 运行参数和配置
            queue: 用于流式传输事件的队列
        """
        try:

            # 推送元数据事件
            await queue.push(EventMessage(
                event="metadata",
                data={
                    "assistant_id": payload.assistant_id,
                }
            ))

            # 配置流模式
            stream_modes = self._normalize_stream_mode(payload.stream_mode)

            # 构建配置
            config = self._build_config(payload)

            # 确定输入
            graph_input = self._prepare_input(payload)

            # 执行图并流式传输事件
            thread_interrupted = False
            async for event in graph.astream(
                graph_input,
                config=config,  # type: ignore
                stream_mode=stream_modes,  # type: ignore
                subgraphs=payload.stream_subgraphs or False,
                context=payload.context  # type: ignore
            ):
                if await self._handle_event(event, queue):
                    thread_interrupted = True

            # 检查执行结果并更新状态
            await self._finalize_execution(thread_interrupted, queue)

        except Exception as e:
            # 处理错误
            await self._handle_error(e, queue)
            raise

    def _normalize_stream_mode(
        self,
        stream_mode: Union[List[StreamMode], StreamMode, None]
    ) -> List[str]:
        """
        规范化流模式参数

        Args:
            stream_mode: 流模式配置

        Returns:
            规范化的流模式列表
        """
        if stream_mode is None:
            return ["values"]
        if isinstance(stream_mode, StreamMode):
            return [stream_mode.value]
        return [mode.value for mode in stream_mode]

    def _prepare_input(self, payload: RunCreateStateless) -> Any:
        """
        准备图的输入

        Args:
            payload: 运行参数

        Returns:
            图的输入数据
        """

        # 使用普通输入
        return payload.input or {}

    def _build_config(
        self,
        payload: RunCreateStateless
    ) -> Dict[str, Any]:
        """
        构建图执行配置

        Args:
            payload: 运行参数

        Returns:
            图执行配置字典
        """
        # 基础配置
        config: Dict[str, Any] = {
            "configurable": {}
        }

        # 合并用户提供的配置
        if payload.config:
            # 合并 configurable
            if payload.config.configurable:
                config["configurable"].update(payload.config.configurable)
            # 添加其他配置项
            if payload.config.tags:
                config["tags"] = payload.config.tags
            if payload.config.recursion_limit is not None:
                config["recursion_limit"] = payload.config.recursion_limit

        return config

    async def _handle_event(
        self,
        event: Any,
        queue: BaseStreamQueue,
    ) -> bool:
        """
        处理图执行事件

        Args:
            event: 图执行产生的事件
            queue: 事件队列

        Returns:
            是否检测到中断事件
        """
        thread_interrupted = False

        # 解析事件格式
        namespace = None
        event_type = "values"  # 默认类型
        event_data = event

        if isinstance(event, tuple) and len(event) == 3:
            # 三元组格式 (namespace, event_type, event_data)
            # 这种格式通常在启用 subgraphs 时出现
            namespace, event_type, event_data = event
        elif isinstance(event, tuple) and len(event) == 2:
            # 二元组格式 (event_type, event_data)
            event_type, event_data = event
        # else: 单值事件，使用默认的 event_type="values", event_data=event

        # 检查是否是中断事件
        # 没有状态，想要判断是否为__interrupt__，只能通过这种方法，所以event_type必需包含values或者updates
        # 不过正常情况下，没有状态的graph不应该包含interrupt
        if isinstance(event_data, dict) and "__interrupt__" in event_data:
            thread_interrupted = True

        # 构建事件消息数据
        if namespace is not None:
            # 包含 namespace 的事件（来自 subgraph）
            message_data = {
                "namespace": namespace,
                "data": event_data
            }
        else:
            # 普通事件
            message_data = event_data

        # 推送事件到队列
        await queue.push(EventMessage(
            event=event_type,
            data=message_data
        ))

        return thread_interrupted

    async def _finalize_execution(
        self,
        thread_interrupted: bool,
        queue: BaseStreamQueue
    ) -> None:
        """
        完成执行并更新最终状态

        Args:
            thread_interrupted: 是否检测到中断事件
            queue: 事件队列
        """
        if thread_interrupted:
            # 执行被中断
            await queue.push(EventMessage(
                event="__stream_end__",
                data={"status": "interrupted"}
            ))
        else:
            # 执行成功完成
            await queue.push(EventMessage(
                event="__stream_end__",
                data={"status": "success"}
            ))

    async def _handle_error(
        self,
        error: Exception,
        queue: BaseStreamQueue
    ) -> None:
        """
        处理执行错误

        Args:
            error: 捕获的异常
            queue: 事件队列
        """
        # 推送错误事件 - 使用 "error" 作为事件名称以符合 LangGraph 规范
        await queue.push(EventMessage(
            event="error",
            data={
                "error": str(error),
                "type": type(error).__name__
            }
        ))
