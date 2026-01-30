import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
    DataPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_agent_parts_message,
    new_task,
)
from a2a.utils.errors import ServerError

from ..services import RunsService
from ..models import RunCreateStateful

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphAgentExecutor(AgentExecutor):
    """GraphAgentExecutor"""

    def __init__(self, assistant_id: str):
        self.assistant_id = assistant_id
        self.runs_service = RunsService()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            # 创建运行配置
            payload = RunCreateStateful(  # type: ignore
                assistant_id=self.assistant_id,
                input={'messages': [('user', query)]},
                if_not_exists="create",
                stream_mode=["messages"],
            )

            # 使用 runs_service 的通用方法执行运行并获取队列
            queue, _ = await self.runs_service.execute_run_to_queue(
                task.context_id,
                payload
            )

            # 处理流式输出
            final_result = None  # 保存最终结果
            async for message in queue.on_data_receive():
                # 根据事件类型处理消息
                if message.event == "messages":
                    # 处理消息事件，提取 content
                    content = self._extract_content_from_messages(message.data)
                    if content:
                        final_result = content
                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(
                                content,
                                task.context_id,
                                task.id,
                            ),
                        )
                elif message.event == "__stream_end__":
                    # 流结束事件
                    if message.data.get("status") == "interrupted":
                        interrupts = message.data.get("interrupts")
                        await updater.update_status(
                            TaskState.input_required,
                            new_agent_parts_message(
                                [Part(root=DataPart(data=i)) for i in interrupts],
                                task.context_id,
                                task.id,
                            ),
                            final=True,
                        )
                        break
                    else:
                        # 成功完成，添加最终结果作为 artifact
                        if final_result:
                            await updater.add_artifact(
                                [Part(root=TextPart(text=final_result))],
                                name='conversion_result',
                            )
                        await updater.complete()
                        break

                elif message.event == "error":
                    # 错误事件，记录详细信息
                    error_info = message.data
                    logger.error(f'Graph execution error: {error_info}')
                    raise ServerError(error=InternalError())

        except Exception as e:
            logger.error(f'An error occurred while streaming the response: {e}')
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        return False

    def _extract_content_from_messages(self, data) -> str:
        """
        从消息数据中提取 content

        Args:
            data: 消息数据

        Returns:
            提取的 content 字符串
        """
        try:
            # 如果是列表，遍历查找包含 content 的项
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'content' in item:
                        return str(item['content'])
            # 如果是字典，直接获取 content
            elif isinstance(data, dict) and 'content' in data:
                return str(data['content'])

            # 如果没有找到 content，返回整个数据的字符串表示
            return str(data)
        except Exception as e:
            logger.error(f'Error extracting content from messages: {e}')
            return str(data)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
