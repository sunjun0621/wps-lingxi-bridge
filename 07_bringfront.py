# -*- coding: utf-8 -*-
# 用 CDP 把指定 target 对应窗口前置（PowerShell 侧解释器，已装 websocket-client）
import json, time, sys
import websocket
ws = websocket.create_connection(sys.argv[1])
ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
time.sleep(0.3)
ws.send(json.dumps({"id": 2, "method": "Page.bringToFront"}))
time.sleep(1.0)
print("bringToFront sent")
