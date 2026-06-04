"""
BettingClient    - 投注用 client
SettlementClient - 結算用 client
"""
import httpx
import requests
from dataclasses import dataclass

BASE_URL = "https://uapextopsq.win"
SETTLEMENT_BASE = "https://ct.supers168.com"

@dataclass
class Session:
    mb_id: str        # 使用者帳號
    login_id: str     # 登入後拿到的 loginID,用作 ssstoken


class BettingClient:
    def __init__(self, timeout: float = 10.0):
        self.http = httpx.Client(base_url=BASE_URL, timeout=timeout)

    def login(self, username: str, password: str) -> Session:
        payload = {"mbID": username, "pw": password}
        resp = self.http.post(
            "/api/mb/sin/login",data=json.dumps(payload)
        )
        resp.raise_for_status()
        data = resp.json()

        # 成功 response 結構: { "code": 200, "data": { "loginID": "..." } }
        if data.get("code") != 200 or not isinstance(data.get("data"), dict):
            raise RuntimeError(f"登入失敗: {data}")

        login_id = data["data"].get("loginID")
        if not login_id:
            raise RuntimeError(f"登入回應缺少 loginID: {data}")

        return Session(mb_id=username, login_id=login_id)

    def place_bet(self, session: Session, cat_id: int,
                  wager_string: str, amount: int,
                  bet_type: int = 1) -> dict:
        payload = {
            "list": [{
                "CatId": cat_id,
                "WagerString": wager_string,
                "Amount": amount,
                "AcceptBetter": True,
                "BetType": bet_type,
                "PlaySource": 0,
            }]
        }
        headers = {
            "ssstoken": session.login_id,
            "sssmbid": session.mb_id,
            "Content-Type": "application/json",
        }
        resp = self.http.post("/api/GameInfo/Play", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self.http.close()


class SettlementClient:
    """結算用 client,用 requests.Session 維持 cookie 認證"""

    def __init__(self, timeout: float = 10.0):
        self.session = requests.Session()
        self.timeout = timeout
        self.logged_in = False

    def login(self, username: str, password: str):
        url = f"{SETTLEMENT_BASE}/api/users/authenticate"
        resp = self.session.post(
            url,
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        if not self.session.cookies:
            raise RuntimeError(f"登入後 cookie 為空: {resp.text}")
        self.logged_in = True

    def settle(self, payload: dict) -> dict:
        if not self.logged_in:
            raise RuntimeError("尚未登入,請先呼叫 login()")
        url = f"{SETTLEMENT_BASE}/api/game/returnA"
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self.session.close()