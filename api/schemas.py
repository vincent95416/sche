"""
api 的 Pydantic v2 資料模型。
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

# ====== modules ======

class PlayInput(BaseModel):
    csv_file: str = Field(..., description="對應的玩家帳號 CSV 檔名,例如 mbA.csv")
    cat_id: int = Field(3, description="玩法分類,籃球=3")
    wager_string: str = Field(..., description="下注字串,完整一行")
    amount: int = Field(100, ge=1, description="下注金額")


class ModuleCreateRequest(BaseModel):
    module_number: int = Field(..., ge=1, le=99, description="module 編號,會寫成 module_NN.py")
    plays: list[PlayInput] = Field(..., min_length=1, description="玩法清單,通常 8 個 (mbA~mbH)")
    users_per_play: int = Field(1, ge=1, description="每個玩法 csv 取前幾位 user 來下注")

    admin_username: str
    admin_password: str
    event_id: str
    league: str
    home_team: str = Field(..., description="主隊名稱;會寫進 PAYLOAD.HomeTeam")
    away_team: str = Field(..., description="客隊名稱;會寫進 PAYLOAD.AwayTeam")
    date: str = Field(..., description='例如 "2026-06-01 00:00"')
    cat_id: int = Field(3, description="玩法分類,籃球=3;會寫進 PAYLOAD.CatID 與 gameEvt.CatID")

    home_score: int = 0
    away_score: int = 0
    fh_home_score: int = 0
    fh_away_score: int = 0

    overwrite: bool = Field(False, description="目標 module_NN.py 已存在時是否覆寫")

    model_config = {
        "json_schema_extra": {
            "example": {
                "module_number": 1,
                "plays": [
                    {"csv_file": f"mb{ch}.csv", "cat_id": 3,
                     "wager_string": f"<填入玩法 {ch} 的下注字串>", "amount": 100}
                    for ch in "ABCDEFGH"
                ],
                "users_per_play": 1,
                "admin_username": "admin",
                "admin_password": "password",
                "event_id": "25844225",
                "league": "NBA",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "date": "2026-06-01 00:00",
                "cat_id": 3,
                "home_score": 0,
                "away_score": 0,
                "fh_home_score": 0,
                "fh_away_score": 0,
                "overwrite": False,
            }
        }
    }


class ModuleCreateResponse(BaseModel):
    module_number: int
    path: str
    overwritten: bool


class ModuleSummary(BaseModel):
    module_number: int
    event_id: str
    league: str
    home_team: str
    away_team: str
    date: str
    play_count: int
    users_per_play: int = 1


# ====== schedules ======

JobKind = Literal["bet", "settle"]


class ScheduleCreateRequest(BaseModel):
    """
    建立一條 Linux crontab 排程。
    cron 五欄全部以字串給,支援 *, */5, 1-5, 1,3,5 等標準語法。
    """
    job_id: Optional[str] = Field(None, description="可選的 job_id,不填會自動產生 8 碼 hex")
    kind: JobKind = Field(..., description="bet=投注 (main.py);settle=結算 (settle.py)")
    module_number: int = Field(..., ge=1, le=99)

    hour: str = Field(..., description='cron hour,例如 "13"(分鐘自動鎖在 00)')
    day: str = Field(..., description='cron day of month,例如 "1"')
    month: str = Field(..., description='cron month,例如 "6"')


class ScheduleInfo(BaseModel):
    job_id: str
    kind: JobKind
    module_number: int
    cron_expr: str
    command: str
