"""
LangGraph执行器
"""

from typing import Any, Dict, List, Union
from langgraph.graph.state import CompiledStateGraph

from ..managers import (
    BaseThreadsManager,
    BaseCheckpointerManager,
    BaseStreamQueue,
    EventMessage,
)
from ..models import RunCreateStateful, ThreadStatus, StreamMode


class GraphExecutor:
    """
    LangGraph 图执行器

    负责执行 LangGraph 图并将事件流式传输到队列中。
    管理线程状态并处理执行生命周期。
    """

    def __init__(
        self,
        thread_manager: BaseThreadsManager,
    ):
        """
        初始化图执行器

        Args:
            thread_manager: 线程管理器，用于更新线程状态
        """
        self.thread_manager = thread_manager

    async def stream_graph(
        self,
        graph: CompiledStateGraph,
        payload: RunCreateStateful,
        queue: BaseStreamQueue,
        thread_id: str,
    ) -> None:
        """
        执行图并流式传输事件

        Args:
            graph: 要执行的 LangGraph 编译图
            payload: 运行参数和配置
            queue: 用于流式传输事件的队列
            thread_id: 线程 ID
        """
        try:
            # 更新线程状态为忙碌
            await self.thread_manager.update(
                thread_id,
                {"status": ThreadStatus.busy}
            )

            # 推送元数据事件
            await queue.push(EventMessage(
                event="metadata",
                data={
                    "thread_id": thread_id,
                    "assistant_id": payload.assistant_id,
                }
            ))

            # 配置流模式
            stream_modes = self._normalize_stream_mode(payload.stream_mode)

            # 构建配置
            config = self._build_config(thread_id, payload)

            # 确定输入：如果提供了 command，使用 command；否则使用 input
            graph_input = self._prepare_input(payload)

            # 执行图并流式传输事件
            async for event in graph.astream(
                graph_input,
                config=config,  # type: ignore
                stream_mode=stream_modes,  # type: ignore
                interrupt_before=payload.interrupt_before,
                interrupt_after=payload.interrupt_after,
                subgraphs=payload.stream_subgraphs or False,
                context=payload.context  # type: ignore
            ):
                await self._handle_event(event, queue, thread_id)

            # 检查执行结果并更新状态
            await self._finalize_execution(thread_id, queue)

        except Exception as e:
            # 处理错误
            await self._handle_error(e, thread_id, queue)
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

    def _prepare_input(self, payload: RunCreateStateful) -> Any:
        """
        准备图的输入

        如果提供了 command，则使用 command（用于恢复中断的执行）；
        否则使用 input。

        Args:
            payload: 运行参数

        Returns:
            图的输入数据
        """
        if payload.command:
            # 使用 Command 恢复中断的执行
            # Command 可以包含 update（状态更新）、resume（传递给中断节点的值）和 goto（控制流）
            from langgraph.types import Command, Send as LangGraphSend

            # 转换 goto 参数
            goto = None
            if payload.command.goto:
                if isinstance(payload.command.goto, str):
                    # 单个节点名称
                    goto = payload.command.goto
                elif isinstance(payload.command.goto, list):
                    # 节点名称列表或 Send 对象列表
                    goto = []
                    for item in payload.command.goto:
                        if isinstance(item, str):
                            goto.append(item)
                        else:
                            # 转换我们的 Send 模型为 LangGraph 的 Send
                            goto.append(LangGraphSend(
                                node=item.node,
                                arg=item.input
                            ))
                else:
                    # 单个 Send 对象
                    goto = LangGraphSend(
                        node=payload.command.goto.node,
                        arg=payload.command.goto.input
                    )

            return Command(
                update=payload.command.update,
                resume=payload.command.resume,
                goto=goto  # type: ignore
            )

        # 使用普通输入
        return payload.input or {}

    def _build_config(
        self,
        thread_id: str,
        payload: RunCreateStateful
    ) -> Dict[str, Any]:
        """
        构建图执行配置

        Args:
            thread_id: 线程 ID
            payload: 运行参数

        Returns:
            图执行配置字典
        """
        # 基础配置
        config: Dict[str, Any] = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # 添加 checkpoint 配置
        if payload.checkpoint:
            if payload.checkpoint.checkpoint_id:
                config["configurable"]["checkpoint_id"] = payload.checkpoint.checkpoint_id
            if payload.checkpoint.checkpoint_ns:
                config["configurable"]["checkpoint_ns"] = payload.checkpoint.checkpoint_ns

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
        thread_id: str,
    ) -> None:
        """
        处理图执行事件

        Args:
            event: 图执行产生的事件
            queue: 事件队列
            thread_id: 线程 ID
        """
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
        if isinstance(event_data, dict) and "__interrupt__" in event_data:
            # 中断事件，更新线程状态为中断
            await self.thread_manager.update(
                thread_id,
                {"status": ThreadStatus.interrupted}
            )

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

    async def _finalize_execution(
        self,
        thread_id: str,
        queue: BaseStreamQueue
    ) -> None:
        """
        完成执行并更新最终状态

        Args:
            thread_id: 线程 ID
            queue: 事件队列
        """
        # 获取当前线程状态
        thread = await self.thread_manager.get(thread_id)

        if thread.status == ThreadStatus.interrupted:
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
            await self.thread_manager.update(
                thread_id,
                {"status": ThreadStatus.idle}
            )

    async def _handle_error(
        self,
        error: Exception,
        thread_id: str,
        queue: BaseStreamQueue
    ) -> None:
        """
        处理执行错误

        Args:
            error: 捕获的异常
            thread_id: 线程 ID
            queue: 事件队列
        """
        # 推送错误事件
        await queue.push(EventMessage(
            event="__stream_error__",
            data={
                "error": str(error),
                "type": type(error).__name__
            }
        ))

        # 更新线程状态为错误
        await self.thread_manager.update(
            thread_id,
            {"status": ThreadStatus.error}
        )
