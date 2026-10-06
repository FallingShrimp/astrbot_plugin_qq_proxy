import asyncio
import time
from collections.abc import AsyncGenerator

from aiocqhttp.exceptions import ActionFailed

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.components import At, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.star.filter.event_message_type import EventMessageType

from .lib import manager
from .lib.models import MessagePart, ModelConfig, ResponseState, ServerConfig
from .lib.server import ProxyServer


class PluginQQProxy(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        manager.server = ServerConfig.model_validate(config["server"])
        manager.default_model = config["default_model"]
        manager.active_time = time.time()
        for model in config["models"]:
            manager.models.append(ModelConfig.model_validate(model))
        for key in config["apikeys"]:
            manager.apikeys.append(key)
        logger.info(f"Models: {manager.models}")
        self.server = ProxyServer(self.model_call)
        self.response: ResponseState | None = None
        self.sessions: dict[str, MessageSession] = {}

    def get_session_key(self, uid: str, group: str | None = None):
        return f"{uid}${group}"

    def get_caller_session(self, model: ModelConfig) -> MessageSession | None:
        logger.info(self.sessions)
        return self.sessions.get(self.get_session_key(model.uid, model.group))

    async def model_call(
        self,
        messages: list[MessagePart],
        model: ModelConfig,
        id: str,
    ) -> AsyncGenerator[str]:
        async def notice(session: MessageSession, message: str):
            try:
                plain = Plain(message)
                await self.context.send_message(
                    session,
                    MessageChain(
                        chain=[At(qq=model.uid), plain]
                        if model.group is not None
                        else [plain]
                    ),
                )
            except ActionFailed:
                logger.error("通知发送失败，可能被禁言了")

        self.response = ResponseState(True, model, id)
        session = self.get_caller_session(model)
        if not session:
            yield '<failed reason="会话尚未被捕获" />'
            return
        await notice(
            session,
            "\n".join(
                [
                    "这是一段情景对话：",
                    "```",
                    *(f"{msg['role']} : {msg['content']}" for msg in messages),
                    "assistant > ...",
                    "```",
                    "请你推测：assistant接下来会怎么回复？",
                ]
            ),
        )
        while self.response.status:
            try:
                yield await self.response.pop(30)
            except TimeoutError:
                self.response.stop()
                break
        await notice(session, "响应已超时")

    @filter.event_message_type(EventMessageType.ALL)
    async def input(self, event: AstrMessageEvent):
        key = self.get_session_key(event.get_sender_id(), event.get_group_id())
        if key not in self.sessions:
            self.sessions[key] = event.session
            logger.info(f"对于{key}的会话{event.get_session_id()}已被捕获")
        if not self.response:
            return
        if not self.response.status:
            return
        if event.get_sender_id() != self.response.source.uid:
            return
        if self.response.source.group is not None:
            if event.get_group_id() != self.response.source.group:
                return
        event.call_llm = True
        event.stop_event()
        self.response.upload(event.message_str)

    @filter.command_group("proxy")
    async def proxy():
        pass

    @proxy.command("stop")
    async def stop_proxy(self, event: AstrMessageEvent):
        if self.response:
            self.response.stop()
            yield event.plain_result(f"响应{self.response.id}已终止")
        else:
            yield event.plain_result("没有响应")

    async def initialize(self) -> None:
        asyncio.create_task(self.server.start())

    async def terminate(self) -> None:
        if self.response:
            self.response.status = False
        await self.server.stop()
