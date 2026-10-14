# -*- coding: utf-8 -*-
# 灵犀云端 assistant 通道客户端：cookie 鉴权，创建会话 + SSE 流式补全
import json, os, time
import requests

BASE = "https://lingxi.wps.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Lingxi Claw/1.3.16 Chrome/144.0.7559.236 Electron/40.8.2 Safari/537.36")


class LingxiError(Exception):
    pass


class LingxiClient:
    def __init__(self, cookies: dict):
        self.cookies = cookies
        self.headers = {
            "Content-Type": "application/json",
            "X-Cc-Version": "1",
            "User-Agent": UA,
            "Referer": "https://lingxi.wps.cn/_desktop/lingxi/",
        }

    @classmethod
    def from_file(cls, path):
        cj = json.load(open(path, encoding="utf-8"))
        cookies = {c["name"]: c["value"] for c in cj
                   if c["host"] in (".wps.cn", "web.wps.cn")
                   and not c["value"].startswith("<")}
        if "wps_sid" not in cookies:
            raise LingxiClient and LingxiError("未在 cookie 文件中找到 wps_sid")
        return cls(cookies)

    def create_session(self):
        r = requests.post(BASE + "/api/aigc/v3/assistant/sessions",
                          headers=self.headers, cookies=self.cookies, json={}, timeout=30)
        j = r.json()
        if j.get("result") != "ok":
            raise LingxiError("创建会话失败: %s" % r.text)
        return j["data"]["session_id"]

    @staticmethod
    def _block_events(block: str):
        event = ""
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        return event, "\n".join(data_lines)

    def stream_chat(self, session_id, question, expect_model=None):
        """yield ('delta', str) | ('error', str)；正常结束自动停止。"""
        body = {"question": question}
        if expect_model:
            body["expect_model"] = expect_model
        url = BASE + f"/api/aigc/v3/assistant/sessions/{session_id}/completions"
        with requests.post(url, headers=self.headers, cookies=self.cookies,
                           json=body, timeout=120, stream=True) as r:
            buf = b""
            for chunk in r.iter_content(256):
                buf += chunk
                while b"\n\n" in buf:
                    block, buf = buf.split(b"\n\n", 1)
                    yield from self._handle_block(block.decode("utf-8", "replace"))
            if buf.strip(b":keepalive").strip():
                yield from self._handle_block(buf.decode("utf-8", "replace"))

    def _handle_block(self, block):
        event, data = self._block_events(block)
        if not data:
            return
        try:
            j = json.loads(data)
        except Exception:
            return
        t = j.get("type")
        if t == "text":
            piece = j.get("data", "") or ""
            if piece:
                yield "delta", piece
        elif event == "error" or j.get("result") == "InvalidArgument":
            yield "error", j.get("msg", "灵犀接口错误")
        # user / text_start / text_end / end / recommend* / finish 无需转发
