import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, Callable

from aiohttp import web

from ..lib import manager
from .models import MessagePart, ModelConfig


class ProxyServer:
    def __init__(
        self,
        model_call: Callable[
            [list[MessagePart], ModelConfig, str], AsyncGenerator[str]
        ],
    ) -> None:
        self.runner: web.AppRunner | None = None
        self.model_call = model_call

    async def chat_complt(self, request: web.Request):
        authorization_head = request.headers.get("Authorization", "")
        if not authorization_head.startswith("Bearer "):
            return web.json_response({"error": "Unauthorized"}, status=401)
        apikey = authorization_head.removeprefix("Bearer ").strip()
        if apikey not in manager.config.server.apikeys:
            return web.json_response({"error": "Unauthorized"}, status=401)
        body: dict = await request.json()

        stream = body.get("stream", False)
        model_id = body.get("model", manager.config.default_model)
        messages: list[MessagePart] = body.get("messages", [])
        response_id = str(uuid.uuid4())
        create_time = int(time.time())

        model_config: ModelConfig | None = None
        for config in manager.config.models:
            if config.id == model_id:
                model_config = config
        if not model_config:
            return web.json_response(
                {"error": f"Not found model {model_id}"}, status=404
            )

        if not stream:
            result = "".join(
                [t async for t in self.model_call(messages, model_config, response_id)]
            )
            return web.json_response(
                {
                    "id": response_id,
                    "object": "chat.completion",
                    "created": create_time,
                    "model": model_id,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": result},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": len(result),
                        "total_tokens": 10 + len(result),
                    },
                }
            )
        else:
            response = web.StreamResponse()
            response.headers["Content-Type"] = "text/event-stream"
            response.headers["Cache-Control"] = "no-cache"
            response.headers["Connection"] = "keep-alive"
            await response.prepare(request)
            async for token in self.model_call(messages, model_config, response_id):
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": create_time,
                    "model": model_id,
                    "choices": [
                        {"index": 0, "delta": {"content": token}, "finish_reason": None}
                    ],
                }
                payload = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await response.write(payload.encode("utf-8"))
            stopchunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": create_time,
                "model": model_id,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            await response.write(
                f"data: {json.dumps(stopchunk, ensure_ascii=False)}\n\n".encode(),
            )
            await response.write(b"data: [DONE]\n\n")
            await response.write_eof()
            return response

    async def getmodels(self, request: web.Request):
        return web.json_response(
            {
                "object": "list",
                "data": [
                    {
                        "id": x.id,
                        "object": "model",
                        "created": manager.active_time,
                        "owned_by": manager.config.server.name,
                    }
                    for x in manager.config.models
                ],
            }
        )

    async def start(self):
        app = web.Application()
        app.add_routes(
            [
                web.post("/v1/chat/completions", self.chat_complt),
                web.get("/v1/models", self.getmodels),
            ]
        )
        runner = web.AppRunner(app)
        self.runner = runner
        await runner.setup()
        await web.TCPSite(
            runner, manager.config.server.host, manager.config.server.port
        ).start()
        await asyncio.Event().wait()

    async def stop(self):
        if not self.runner:
            return
        await self.runner.cleanup()
