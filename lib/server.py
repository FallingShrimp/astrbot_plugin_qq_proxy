import asyncio
import json
import uuid

from aiohttp import web

from .manager import apikeys


class ProxyServer:
    def __init__(self) -> None:
        self.runner: web.AppRunner | None = None

    async def chat_completions_handler(self, request: web.Request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response({"error": "Unauthorized"}, status=401)
        api_key = auth_header.removeprefix("Bearer ").strip()
        if api_key not in apikeys:
            return web.json_response({"error": "Unauthorized"}, status=401)
        body = await request.json()
        stream = body.get("stream", False)
        model = body.get("model", "gpt-3.5-turbo")
        messages = body.get("messages", [])
        response_id = f"chatcmpl-{uuid.uuid4()}"
        if not stream:
            full_text = "".join([t async for t in mock_llm_stream(messages)])
            resp_data = {
                "id": response_id,
                "object": "chat.completion",
                "created": 1735688967,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": full_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": len(full_text),
                    "total_tokens": 10 + len(full_text),
                },
            }
            return web.json_response(resp_data)
        else:
            resp = web.StreamResponse()
            resp.headers["Content-Type"] = "text/event-stream"
            resp.headers["Cache-Control"] = "no-cache"
            resp.headers["Connection"] = "keep-alive"
            await resp.prepare(request)
            created = 1735688967
            # 逐token发送chunk
            async for token in mock_llm_stream(messages):
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {"index": 0, "delta": {"content": token}, "finish_reason": None}
                    ],
                }
                # SSE格式：data: {json}\n\n
                payload = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await resp.write(payload.encode("utf-8"))

            # 结束块 finish_reason=stop
            end_chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            await resp.write(
                f"data: {json.dumps(end_chunk, ensure_ascii=False)}\n\n".encode()
            )
            # 最后的 [DONE]
            await resp.write(b"data: [DONE]\n\n")
            await resp.done()
            return resp

    async def start(self):
        app = web.Application()
        app.add_routes(
            [web.post("/v1/chat/completions", self.chat_completions_handler)],
        )
        runner = web.AppRunner(app)
        self.runner = runner
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", 8000).start()
        await asyncio.Event().wait()
