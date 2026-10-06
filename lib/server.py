import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, Callable

from aiohttp import web

from ..lib import manager
from .models import ModelConfig


class ProxyServer:
    def __init__(
        self, model_call: Callable[[ModelConfig], AsyncGenerator[str]]
    ) -> None:
        self.runner: web.AppRunner | None = None
        self.model_call = model_call

    async def chat_complt(self, request: web.Request):
        authorization_head = request.headers.get("Authorization", "")
        if not authorization_head.startswith("Bearer "):
            return web.json_response({"error": "Unauthorized"}, status=401)
        apikey = authorization_head.removeprefix("Bearer ").strip()
        if apikey not in manager.apikeys:
            return web.json_response({"error": "Unauthorized"}, status=401)
        body: dict = await request.json()
        stream = body.get("stream", False)
        model = body.get("model", manager.default_model)
        messages = body.get("messages", [])
        response_id = uuid.uuid4()
        create_time = int(time.time())
        if not stream:
            result = "".join([t async for t in self.model_call(messages)])
            return web.json_response(
                {
                    "id": response_id,
                    "object": "chat.completion",
                    "created": create_time,
                    "model": model,
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
            async for token in self.model_call(messages):
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": create_time,
                    "model": model,
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
                "model": model,
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
                        "owned_by": manager.server.name,
                    }
                    for x in manager.models
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
        await web.TCPSite(runner, "0.0.0.0", 8000).start()
        await asyncio.Event().wait()
