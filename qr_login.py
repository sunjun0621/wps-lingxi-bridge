# -*- coding: utf-8 -*-
"""WPS 账号扫码登录（网页端流程，免本地签名）。

流程：
  PKCE -> GET qr.wps.cn/api/v3/login_qrcode 得 loginid
       -> GET .../login_qrcode/url 得二维码图片
       -> 轮询 .../login_qrcode/login (state=scan -> confirm) 得 kso_authcode
       -> POST account.wps.cn/passport/secure/api/grant_token 换 wps_sid (Set-Cookie)
"""
import requests, hashlib, base64, os, json

QR = "https://qr.wps.cn"
ACCOUNT = "https://account.wps.cn"
BUSINESS = "https://lingxi.wps.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def new_pkce():
    verifier = b64url(os.urandom(40))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def _cookie_value(resp, name):
    """优先 requests cookies，失败再手动解析 Set-Cookie。"""
    if name in resp.cookies:
        return resp.cookies[name]
    raw = resp.headers.get("set-cookie", "") or ""
    # requests 只暴露合并后的头；多 Set-Cookie 时用 raw 的属性
    try:
        for c in resp.raw.headers.get_all("Set-Cookie"):
            for part in c.split(";"):
                if part.strip().startswith(name + "="):
                    return part.strip().split("=", 1)[1]
    except Exception:
        pass
    for part in raw.split(";"):
        if part.strip().startswith(name + "="):
            return part.strip().split("", 1) if False else part.strip().split("=", 1)[1]
    return None


class QrSession:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.s.headers["Referer"] = ACCOUNT + "/"
        self.loginid = None
        self.verifier = self.challenge = None
        self.qr_url = None

    def start(self):
        self.verifier, self.challenge = new_pkce()
        r = self.s.get(QR + "/api/v3/login_qrcode",
                       params={"code_challenge": self.challenge}, timeout=30)
        o = r.json()
        if o.get("result") != "ok":
            raise RuntimeError("取二维码失败: " + r.text[:200])
        self.loginid = o["loginid"]
        r2 = self.s.get(QR + "/api/v3/login_qrcode/url",
                        params={"loginid": self.loginid, "data": json.dumps({})},
                        timeout=30)
        uo = r2.json()
        if uo.get("result") != "ok":
            raise RuntimeError("取二维码图片失败: " + r2.text[:200])
        self.qr_url = uo["url"]
        return {"loginid": self.loginid, "qr_url": self.qr_url}

    def poll(self, phase):
        """phase: 'scan'（等待扫码）或 'confirm'（已扫码，等待手机确认）。"""
        r = self.s.get(QR + "/api/v3/login_qrcode/login",
                       params={"loginid": self.loginid, "state": phase}, timeout=40)
        return r.json()

    def grant(self, kso_authcode):
        body = {"grant_type": "authorization_code", "code": kso_authcode,
                "code_verifier": self.verifier, "login_scenario": "qr", "slv": "none"}
        r = self.s.post(ACCOUNT + "/passport/secure/api/grant_token",
                        json=body,
                        headers={"Content-Type": "application/json",
                                 "Origin": BUSINESS, "Referer": BUSINESS + "/"},
                        timeout=30, allow_redirects=False)
        sid = _cookie_value(r, "wps_sid")
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:300]}
        return data, sid, r.status_code


def check_session(sid):
    """返回当前登录账号信息；未登录返回 None。"""
    r = requests.post(ACCOUNT + "/p/auth/check",
                      headers={"User-Agent": UA, "Cookie": "wps_sid=" + sid,
                               "Origin": BUSINESS, "Referer": BUSINESS + "/",
                               "Accept": "application/json"},
                      timeout=8, allow_redirects=False)
    try:
        o = r.json()
    except Exception:
        return None
    if isinstance(o, dict) and o.get("result") == "ok":
        return {"result": "ok",
                "user_id": o.get("userid") or o.get("user_id") or o.get("uid"),
                "nickname": o.get("nickname") or o.get("user_name") or o.get("name"),
                "avatar": o.get("pic") or o.get("avatar") or o.get("avatar_url"),
                "phone": o.get("phonenumber"), "is_plus": o.get("is_plus")}
    return None
