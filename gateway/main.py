# -*- coding: utf-8 -*-
# OpenAI 兼容反代网关：把 WPS 灵犀 assistant 通道暴露为 /v1/chat/completions
import json, os, time, hashlib, uuid

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from lingxi_client import LingxiClient

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.environ.get("LINGXI_COOKIE_FILE",
                             os.path.join(HERE, "..", "cookies_decrypted.json"))
client = LingxiClient.from_file(COOKIE_FILE)

app = FastAPI(title="Lingxi Reverse Gateway", version="0.1.0")

# assistant 通道固定模型；id 用 wps-ai，附带常见别名
MODELS = [
    {"id": "wps-ai", "object": "model", "created": 0, "owned_by": "wps-lingxi"},
]
MODEL_IDS = {"wps-ai", "model-s", "lingxi", "wps"}

# 进程内会话映射：历史消息指纹 -> 灵犀 session_id，实现连续多轮
_session_store = {}


def flatten_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text":
                    parts.append(c.get("text", ""))
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(p for p in parts if p)
    return ""


def fingerprint(messages):
    raw = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def sse_chunk(model, content=None, finish_reason=None, cmpl_id=None):
    delta = {}
    if content is not None:
        delta["content"] = content
    choice = {"index": 0, "delta": delta, "finish_reason": finish_reason}
    obj = {"id": cmpl_id, "object": "chat.completion.chunk",
           "created": CREATED, "model": model, "choices": [choice]}
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


CREATED = int(time.time())


async def resolve_session(messages):
    before = fingerprint(messages[:-1])
    sid = _session_store.get(before)
    if not sid:
        sid = await anyio.to_thread.run_sync(client.create_session)
    return sid


def remember(sid, messages, answer):
    # 用“用户消息 + 灵犀真实回复”的完整序列存指纹，与下一轮客户端历史口径一致
    full = messages + [{"role": "assistant", "content": answer}]
    _session_store[fingerprint(full)] = sid
    _session_store[fingerprint(messages)] = sid


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": MODELS}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    model = payload.get("model", "wps-ai")
    messages = payload.get("messages", [])
    stream = bool(payload.get("stream", False))
    if not messages:
        return JSONResponse(status_code=400,
                            content={"error": {"message": "messages 不能为空", "type": "invalid_request_error"}})

    question = flatten_content(messages[-1].get("content"))
    sid = await resolve_session(messages)
    cmpl_id = "chatcmpl-" + uuid.uuid4().hex[:24]

    def gen():
        yield sse_chunk(model, content="", cmpl_id=cmpl_id)
        text = ""
        for kind, val in client.stream_chat(sid, question):
            if kind == "delta":
                text += val
                yield sse_chunk(model, content=val, cmpl_id=cmpl_id)
            elif kind == "error":
                err = {"error": {"message": "上游灵犀错误: " + str(val), "type": "upstream_error"}}
                yield "data: " + json.dumps(err, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
                return
        yield sse_chunk(model, finish_reason="stop", cmpl_id=cmpl_id)
        yield "data: [DONE]\n\n"
        remember(sid, messages, text)

    if stream:
        return StreamingResponse(iterate_in_threadpool(gen()),
                                 media_type="text/event-stream")

    # 非流式：同步聚合灵犀返回
    text = ""
    err = None
    for kind, val in client.stream_chat(sid, question):
        if kind == "delta":
            text += val
        elif kind == "error":
            err = val
    if err:
        return JSONResponse(status_code=502,
                            content={"error": {"message": "上游灵犀错误: " + str(err), "type": "upstream_error"}})
    remember(sid, messages, text)
    return {
        "id": cmpl_id, "object": "chat.completion", "created": CREATED, "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
    }
