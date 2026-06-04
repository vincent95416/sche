"""
建立 / 列出 / 查詢 / 刪除 module/module_NN.py。

寫出的檔案 schema 跟既有的 module_XX.py 一致 (PLAYS, ADMIN_*, EVENT_ID, ...,
PAYLOAD_HALF / PAYLOAD_FULL),這樣 main.py / settle.py 可以原樣讀。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from .schemas import ModuleCreateRequest, ModuleSummary, PlayInput

MODULE_DIR = Path(__file__).resolve().parent.parent / "module"


# ---------- 渲染 ----------

def _py_repr(value) -> str:
    return repr(value)


def _render_play(idx: int, play: PlayInput) -> str:
    return (
        f"PLAY_{idx:02d} = {{\n"
        f'    "csv_file": {_py_repr(play.csv_file)},\n'
        f'    "cat_id": {play.cat_id},\n'
        f'    "wager_string": {_py_repr(play.wager_string)},\n'
        f'    "amount": {play.amount},\n'
        f"}}"
    )


def _render_payload(req: ModuleCreateRequest, settle_type: int,
                    is_fh_finish: int, score_ext: int) -> str:
    fh_str = f"{req.fh_home_score}:{req.fh_away_score}"
    return f"""{{
  "EvtID": EVENT_ID,
  "CatID": {req.cat_id},
  "ScheduleTime": DATE,
  "HomeScore": {req.home_score},
  "AwayScore": {req.away_score},
  "FHHomeScore": {req.fh_home_score},
  "FHAwayScore": {req.fh_away_score},
  "CalType": 0,
  "Remark": "",
  "note": "",
  "GetFirst": None,
  "GetEnd": None,
  "SettleType": {settle_type},
  "LeagueName": LEAGUE,
  "HomeTeam": HOME_TEAM,
  "AwayTeam": AWAY_TEAM,
  "IsFullFinish": 0,
  "IsFHFinish": {is_fh_finish},
  "IsGetFirstFinish": 0,
  "IsGetEndFinish": 0,
  "IsAllFinish": 0,
  "ScoreExt": {score_ext},
  "gameEvt": {{
    "LSort": 0,
    "EvtType": 0,
    "HdpInfo": None,
    "IsHot": 0,
    "MatchID": 0,
    "EvtStatus": 0,
    "WagerGrpID": None,
    "WagerTypeID": None,
    "WagerPos": None,
    "Amount": 0,
    "TCount": 0,
    "RCount": 0,
    "IsFullFinish": 0,
    "IsFHFinish": 0,
    "IsGetFirstFinish": 0,
    "IsGetEndFinish": 0,
    "IsAllFinish": 0,
    "Start": 0,
    "ADate": None,
    "LeagueName": LEAGUE,
    "EvtID": EVENT_ID,
    "ScheduleTime": DATE,
    "Team": None,
    "AwayTeam": AWAY_TEAM,
    "HomeTeam": HOME_TEAM,
    "AwayDonID": None,
    "HomeDonID": None,
    "Gtype": None,
    "AwayID": 0,
    "HomeID": 0,
    "LeagueID": None,
    "CatName": None,
    "CatID": {req.cat_id},
    "GameType": None,
    "HomePtid": None,
    "AwayPtid": None,
    "issecondevt": None,
    "SubID": None,
    "Mid_10_1": None,
    "Mid_10_2": None,
    "Mid_10_3": None,
    "MidS1": None,
    "MidS2": None,
    "MidS3": None,
    "Mid_0_1": None,
    "Mid_0_2": None,
    "Mid_0_3": None,
    "Mid_11_1": None,
    "Mid_11_2": None,
    "Mid_11_3": None,
    "FH": {_py_repr(fh_str)},
    "RMid": None,
    "RDateTime": None,
    "RCMid": None,
    "RCDateTime": None,
    "AcqFSite": None,
    "HAcqFSite": None,
    "HomeScore": None,
    "AwayScore": None
  }}
}}"""


def render_module_source(req: ModuleCreateRequest) -> str:
    plays_src = "\n\n".join(
        _render_play(i, p) for i, p in enumerate(req.plays, start=1)
    )
    plays_list = ", ".join(f"PLAY_{i:02d}" for i in range(1, len(req.plays) + 1))

    payload_half = _render_payload(req, settle_type=2, is_fh_finish=0, score_ext=1)
    payload_full = _render_payload(req, settle_type=1, is_fh_finish=1, score_ext=0)

    return f'''"""
資料模組 {req.module_number:02d} - 由 api 自動產生
"""

# ========玩法區 (投注)==========
{plays_src}

PLAYS = [{plays_list}]
USERS_PER_PLAY = {req.users_per_play}


# ========結算區==========
ADMIN_USERNAME = {_py_repr(req.admin_username)}
ADMIN_PASSWORD = {_py_repr(req.admin_password)}
EVENT_ID = {_py_repr(req.event_id)}
LEAGUE = {_py_repr(req.league)}
HOME_TEAM = {_py_repr(req.home_team)}
AWAY_TEAM = {_py_repr(req.away_team)}
DATE = {_py_repr(req.date)}

PAYLOAD_HALF = {payload_half}

PAYLOAD_FULL = {payload_full}
'''


# ---------- 寫檔 ----------

def write_module_file(req: ModuleCreateRequest) -> tuple[Path, bool]:
    """寫 module_NN.py。回傳 (path, 是否覆寫了舊檔)。"""
    MODULE_DIR.mkdir(parents=True, exist_ok=True)
    target = MODULE_DIR / f"module_{req.module_number:02d}.py"
    existed = target.exists()
    if existed and not req.overwrite:
        raise FileExistsError(f"{target.name} 已存在,要覆寫請帶 overwrite=true")
    target.write_text(render_module_source(req), encoding="utf-8")
    return target, existed


# ---------- 讀摘要 ----------

_FILENAME_RE = re.compile(r"^module_(\d{2})\.py$")


def _load_summary(n: int) -> ModuleSummary:
    target = MODULE_DIR / f"module_{n:02d}.py"
    if not target.exists():
        raise FileNotFoundError(f"module_{n:02d}.py 不存在")
    spec = importlib.util.spec_from_file_location(f"_calc_summary_{n:02d}", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return ModuleSummary(
        module_number=n,
        event_id=getattr(mod, "EVENT_ID", ""),
        league=getattr(mod, "LEAGUE", ""),
        home_team=getattr(mod, "HOME_TEAM", getattr(mod, "TEAM_A", "")),
        away_team=getattr(mod, "AWAY_TEAM", getattr(mod, "TEAM_B", "")),
        date=getattr(mod, "DATE", ""),
        play_count=len(getattr(mod, "PLAYS", [])),
        users_per_play=getattr(mod, "USERS_PER_PLAY", 1),
    )


def get_module(n: int) -> ModuleSummary:
    return _load_summary(n)


def list_modules() -> list[ModuleSummary]:
    if not MODULE_DIR.exists():
        return []
    summaries: list[ModuleSummary] = []
    for path in sorted(MODULE_DIR.glob("module_*.py")):
        m = _FILENAME_RE.match(path.name)
        if not m:
            continue
        try:
            summaries.append(_load_summary(int(m.group(1))))
        except Exception:
            # 壞掉的 module 跳過,別整批掛掉
            continue
    return summaries


# ---------- 刪檔 ----------

def delete_module(n: int) -> bool:
    target = MODULE_DIR / f"module_{n:02d}.py"
    if not target.exists():
        return False
    target.unlink()
    return True
