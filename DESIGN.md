# settlement 專案設計文件

## 1. 專案概觀

- `main.py`：以多個帳號併發 (序列) 對同一場賽事下注。
- `settle.py`：賽事結束後，由管理者帳號送出**半場結算**與**全場結算**。

兩者共用同一份「資料模組」(`module/module_XX.py`)，因為投注與結算對應的是**同一場賽事、同一天的劇本**。

```
┌─────────────────────┐         ┌─────────────────────┐
│      main.py        │         │      settle.py      │
│  (批次投注 / 玩家端) │         │  (賽後結算 / 管理端) │
└─────────┬───────────┘         └─────────┬───────────┘
          │                               │
          │     共用同一份 module_XX.py     │
          │   (PLAYS / EVENT_ID / PAYLOADs) │
          ▼                               ▼
   ┌───────────────────────────────────────────┐
   │  client.py                                │
   │  ┌─────────────────┐ ┌──────────────────┐ │
   │  │ BettingClient   │ │ SettlementClient │ │
   │  │ (httpx, token)  │ │ (requests, cookie│ │
   │  └─────────────────┘ └──────────────────┘ │
   └───────────────────────────────────────────┘
                │                       │
        queen168.net              ct.queen168.net
        /api/mb/sin/login         /api/users/authenticate
        /api/GameInfo/Play        /api/game/returnA
```

---

## 2. 目錄結構

```
settlement/
├── main.py              # 投注主程式 (CLI 入口)
├── settle.py            # 結算主程式 (CLI 入口)
├── client.py            # HTTP client (BettingClient / SettlementClient)
├── config.py            # 共用設定 (路徑、密碼、sleep、人數上限)
├── requirements.txt     # httpx, requests
│
├── module/              # 「劇本」資料模組,一場賽事一個檔
│   ├── __init__.py
│   ├── module_01.py     # 內含 PLAYS、ADMIN、EVENT_ID、PAYLOAD_HALF/FULL
│   ├── module_02.py
│   └── ... module_10.py
│
├── csv_data/            # 玩家帳號清單 (一檔一個玩法)
│   ├── mbA.csv          # 玩法 1 用的帳號
│   ├── mbB.csv          # 玩法 2 用的帳號
│   └── ... mbH.csv
│
└── logs/                # 執行紀錄 (依模組編號 + 時間戳命名)
    ├── run_moduleXX_YYYYMMDD_HHMMSS.log
    ├── settle_moduleXX_YYYYMMDD_HHMMSS.log
    └── failed_playN_YYYYMMDD_HHMMSS.csv   # 投注失敗的帳號清單
```

---

## 3. 核心模組設計

### 3.1 `config.py` — 共用設定

| 設定項 | 預設 | 說明 |
|---|---|---|
| `CSV_DIR` | `./csv_data` | 帳號 CSV 來源 |
| `LOG_DIR` | `./logs` | log 與失敗清單輸出位置 |
| `DEFAULT_PASSWORD` | `v1_\WH|P}T4` | 所有玩家帳號共用的固定密碼 |
| `USERS_PER_PLAY` | `300` | 每個玩法最多取前 N 個帳號 |
| `SLEEP_AFTER_LOGIN` | `2.0` | 每位玩家登入後等待秒數 |
| `SLEEP_AFTER_BET` | `2.0` | 每位玩家投注後等待秒數 |

### 3.2 `client.py` — HTTP 通訊層

兩個 client 故意分離，因為**兩個系統的網域、認證方式不同**。

#### `BettingClient` (玩家端 / `queen168.net`)
- 底層：`httpx.Client`
- 認證：登入後拿 `loginID` → 投注時放在 header `ssstoken` + `sssmbid`
- 主要方法：
  - `login(username, password) -> Session`
  - `place_bet(session, cat_id, wager_string, amount, bet_type=1) -> dict`
- `Session` dataclass：`mb_id` (帳號) + `login_id` (token)

#### `SettlementClient` (管理端 / `ct.queen168.net`)
- 底層：`requests.Session` (需要保留 cookie)
- 認證：登入後伺服器回 Set-Cookie，後續呼叫沿用 session cookie
- 主要方法：
  - `login(username, password)`
  - `settle(payload) -> dict`

### 3.3 `module/module_XX.py` — 一場賽事的劇本

一個模組同時承載**投注劇本**與**結算劇本**：

```python
# ===== 投注區 =====
PLAY_01 = {
    "csv_file": "mbA.csv",         # 用哪個帳號清單
    "cat_id": 3,                   # 玩法分類 (籃球=3)
    "wager_string": "3,EVT_ID,103,0,1,1,PK,0.95,HK",
    "amount": 100,
}
# ... PLAY_02 ~ PLAY_08
PLAYS = [PLAY_01, ..., PLAY_08]    # 主程式照順序跑

# ===== 結算區 =====
ADMIN_USERNAME = "Vincent"
ADMIN_PASSWORD = "..."
EVENT_ID = "25844225"
LEAGUE = "NBA G聯盟"
TEAM_A, TEAM_B = "...", "..."
DATE = "2026-05-31 00:00"

PAYLOAD_HALF = { "EvtID": EVENT_ID, "SettleType": 2, ... }  # 半場
PAYLOAD_FULL = { "EvtID": EVENT_ID, "SettleType": 1, ... }  # 全場
```

**慣例**：8 個玩法 ↔ 8 個 CSV (`mbA`~`mbH`) 是固定對應；不同模組之間差異主要在 `EVENT_ID`、隊伍名、wager_string 中的賽事 ID。新版的 `module_10.py` 已開始將 `GAME_ID1~8` 抽成常數，減少手動修改字串時出錯。

### 3.4 `main.py` — 投注主程式

```
python main.py <module_number>     # e.g. python main.py 1
```

執行流程：
1. 解析 CLI 參數 → `importlib` 動態載入 `module.module_NN`
2. 建立 log 檔 (`run_moduleNN_<timestamp>.log`)
3. 依 `PLAYS` 順序，逐個玩法執行：
   - 從對應 CSV 讀前 `USERS_PER_PLAY` 個帳號
   - 對每位帳號：登入 → sleep 2s → 下注 → sleep 2s
   - 失敗者記入 `failed_playN_<timestamp>.csv`
4. 收尾關閉 client

**設計細節**：
- CSV 用 `utf-8-sig` 讀，並濾掉所有空白字元，避免 BOM / 全形空白讓帳號比對失敗。
- 單一玩家失敗不會中斷整個玩法 (`try/except + continue`)，但會被記下來事後排查。
- 全程 logging 同時輸出檔案 + console，便於即時觀察與事後追蹤。

### 3.5 `settle.py` — 結算主程式

```
python settle.py <module_number>   # 1~4 (目前 hard-code 的範圍)
```

執行流程：
1. 動態載入 `module.module_NN`
2. 用 `ADMIN_USERNAME / ADMIN_PASSWORD` 登入 settlement 系統
3. 打 `PAYLOAD_HALF` (半場) → 看 `result == 1` 才算成功
4. **不管半場成功與否**，繼續打 `PAYLOAD_FULL` (全場)
5. 結尾印出 `半場=OK/FAIL, 全場=OK/FAIL`

**設計細節**：
- 半場與全場是「獨立判讀」，刻意不短路；因為兩者邏輯獨立，避免半場小失誤導致全場漏結算。
- 結算 payload 內嵌完整 `gameEvt` 結構是後端要求 — 大量欄位是 `None` 但必須存在，所以 module 必須完整保留這個 schema。

---

## 4. 執行範例

```bash
# 一場賽事的完整流程

# 1) 比賽前：跑投注 (module_03 是這場賽事的劇本)
python main.py 3
#   → 依序為 mbA~mbH 各 300 個帳號下 8 種注
#   → 輸出 logs/run_module03_20260514_120000.log

# 2) 比賽結束後：跑結算
python settle.py 3
#   → 半場、全場各打一次,輸出 logs/settle_module03_*.log
```

---

## 5. 已知限制 / 改善空間

| 類別 | 問題 | 影響 |
|---|---|---|
| **效能** | 序列執行 (login + bet + 4s sleep)，300 帳號 × 8 玩法 ≈ 完整跑完需要數小時 | 接近開賽時很難全部投完 |
| **韌性** | 登入 token / cookie 沒重試、沒指數退避；網路波動就失敗 | 失敗率受網路狀況影響 |
| **安全** | `DEFAULT_PASSWORD`、`ADMIN_PASSWORD` 寫死在原始碼 | 不該進版控、應改 env var |
| **參數** | `settle.py` hard-code 限制 1~4，但 module 已到 10；`main.py` 沒這個限制，行為不一致 | 改 module 數時要兩邊同步 |
| **驗證** | `module_XX.py` 沒有 schema 驗證；wager_string 打錯字 `place_bet` 才會炸 | 排錯成本高 |
| **可觀測性** | 沒有彙總報表 (成功率、各玩法統計、總耗時) | 跑完只能 grep log |
| **乾跑** | 沒有 dry-run 模式可預覽會打哪些請求 | 第一次跑新 module 風險高 |
| **重跑** | 失敗清單存了，但沒有「只重跑失敗者」的指令 | 要手動把 CSV 換掉 |

---

## 6. 設計哲學摘要

1. **資料 / 邏輯分離**：每場賽事 = 一個 module 檔；程式碼幾乎不用動。
2. **投注與結算共用劇本**：避免「賽事 ID 改了但結算還用舊的」這類錯位。
3. **fail-soft**：單一玩家、單一階段失敗都不中斷整體流程，而是落到 log/CSV。
4. **CLI 一個整數選 module**：簡單到不會用錯；自動化排程也好包。

---

## 7. FastAPI 整合層 (`api/`)

獨立 FastAPI service 的 API 層。
**core (client/config/main/settle/module/csv_data) 完全不動**，`api/` 只負責兩件事：

- 建立 / 管理 `module_NN.py` 檔
- 建立 / 管理 Linux crontab 觸發器

### 7.1 目錄結構

```
settlement/                  # 直接就是 service 根目錄 (cwd)
├── app.py                   # FastAPI app 入口 (uvicorn app:app)
├── (core — 不動)
└── api/
    ├── __init__.py           # 對外只匯出一個 router (prefix=/api/crontab)
    ├── schemas.py            # Pydantic v2 models
    ├── module_store.py       # module_NN.py 的 CRUD (檔案層)
    ├── scheduler.py          # crontab CRUD (透過 python-crontab)
    └── routers/
        ├── __init__.py
        ├── modules.py        # /modules 端點
        └── schedules.py      # /schedules 端點
```

### 7.2 路由總覽

```
POST   /api/crontab/modules               建立 / 覆寫 module_NN.py
GET    /api/crontab/modules               列出所有 module 摘要
GET    /api/crontab/modules/{n}           單一 module 摘要 (EVENT_ID/LEAGUE/隊伍/日期/玩法數)
DELETE /api/crontab/modules/{n}           刪除 module_NN.py

POST   /api/crontab/schedules             新增一條 crontab (回傳 job_id)
GET    /api/crontab/schedules             列出我們管理的 crontab
DELETE /api/crontab/schedules/{job_id}    刪除指定 crontab
```

### 7.3 模組產生器 (`module_store.py`)

- 輸入：`ModuleCreateRequest` (玩法清單 + 結算欄位 + 比分)。
- 輸出：寫到 `module/module_NN.py`，schema 跟手寫的模組完全一致 (`PLAYS`、`ADMIN_*`、`EVENT_ID`、`LEAGUE`、`TEAM_A/B`、`DATE`、`PAYLOAD_HALF/FULL`)。
- 讀摘要時用 `importlib.util.spec_from_file_location` 動態載入，避開硬解析 .py。
- 已存在的檔要覆寫須帶 `overwrite=true`，否則 409。
- **PAYLOAD 是自動生成不是 user 帶入**：`PAYLOAD_HALF` / `PAYLOAD_FULL` 加起來 ~60 個欄位,大部分是 `None`(後端 schema 需求),由 `_render_payload(req, settle_type, is_fh_finish, score_ext)` 從 request 上幾個 scalar 欄位(`event_id`、`league`、`team_a/b`、`date`、`*_score`、`cat_id`)組出來;HALF / FULL 只差三個常數 — `(settle_type, is_fh_finish, score_ext) = (2,0,1)` vs `(1,1,0)`,其餘共用。
- **`cat_id` 已開放成 request 欄位**(預設 3 = 籃球),寫進 `PAYLOAD.CatID` 與 `gameEvt.CatID`。但 PAYLOAD 的**整體 shape 仍是籃球專用**(`FH`、`FHHomeScore` 等半場概念),其他 sport 可填 `cat_id` 但 shape 不對 — 多 sport 真正支援要等未來引入「per-sport renderer」(見 §8.3)。

### 7.4 排程器 (`scheduler.py`)

- 走 **Linux 系統 crontab**，套件用 `python-crontab` (`CronTab(user=True)`)。
- 每條我們管的行尾加 tag `# set-job:<8碼hex>`，**只動有這個 tag 的行**，使用者既有 crontab 不受影響。
- 觸發時實際命令：
  ```
  cd <REPO_ROOT> && <PYTHON_BIN> {main.py|settle.py} <NN> >> logs/cron.log 2>&1
  ```
- 路徑動態抓：
  - `REPO_ROOT = Path.cwd()` (預期從 settlement 根目錄起 service，即 settlement 自己)
  - `PYTHON_BIN = sys.executable` (確保與 webservice 同一個 venv)
- **排程精度鎖到「小時整點」**：`ScheduleCreateRequest` 只開放 `hour` / `day` / `month` 三個欄位且**全部必填**；`minute` 內部固定 `"0"`、`day_of_week` 內部固定 `"*"`,使用者填不到。
  - 例:`hour="13", day="1", month="6"` → cron 表示式 `0 13 1 6 *`(6/1 下午 1 點整觸發)
  - 一個 schedule = 一條 cron = 一個動作(bet 或 settle);要完整一場賽事自動化就 POST 兩次
- 一次性排程 (例如「2026-06-01 13:30 跑一次」) 因 crontab 不支援，本層**只做週期性 cron**；若日後要一次性，再加 `at` 或回頭考慮 APScheduler。

### 7.5 啟動方式 (獨立 service)

```powershell
cd C:\path\settlement
uvicorn app:app --host 0.0.0.0 --port 8022
```

- `settlement/` 即 service 根目錄，**自身不是 Python package**（沒有根 `__init__.py`)；最上層各模組以 absolute import 互相引用（`from client import ...`、`from api import router`）。
- 依賴用 `pip install -r requirements.txt`（或對應 `pyproject.toml` 的 dependencies），**不要也不需要** `pip install -e .`。
- 跟其他 service 共存時靠 port 隔離，不走 `include_router` 嵌入。
- cron 觸發的是另一個 process，與 webservice 完全隔離；API 本身只做檔案 / crontab 讀寫，瞬時完成不用鎖。

### 7.6 設計取捨

| 取捨 | 結論 | 理由 |
|---|---|---|
| 排程器 | Linux crontab (非 APScheduler) | 好用 shell 直接改、跨進程獨立、跟既有運維習慣一致 |
| crontab tag | `# set-job:<id>` | 跟使用者其他 crontab 共存不互相踩 |
| 密碼 | 維持渲染進 module_NN.py | 帳密本身已是亂數，沒有抽 env 的必要 |
| csv_data | 寫死在 `settlement/csv_data/` | 保持 core 原樣，不額外做上傳 API |
| Pydantic | v2 (`list[X] + min_length`) | 對齊現代 FastAPI；若 host 是 v1 再調 `min_items` |
| `module_store` vs 舊 `module_generator` | 改名 `module_store` | 多了 list/get/delete，不只是「產生」 |

---

## 8. 目前進度 (Status，更新於 2026-05-28)

> **方向變更 (2026-05-25)**：原本規劃整合進外部 E2E test FastAPI repo (走 `include_router`)；後續評估整合摩擦太大，決定 **settlement 獨立成 service**。
>
> **進一步調整 (2026-05-28)**：`settlement/` 直接作為 service 根目錄，**不再是 Python package**（移除根 `__init__.py`、`settle_service.egg-info/`、`pyproject.toml` 的 `[project.scripts]` / `packages.find`）；最上層 `app.py` / `main.py` / `settle.py` 改用 absolute import。
>
> 對應調整：
> - `app.py` — FastAPI app 入口，從 settlement 根目錄起：`uvicorn app:app`
> - `main.py` / `settle.py` — CLI 改成 `python main.py <NN>` / `python settle.py <NN>`
> - `scheduler.py` 的 cron 觸發命令改成 `cd <root> && python {main.py|settle.py} <NN> >> logs/cron.log`，`REPO_ROOT = Path.cwd()` 即 settlement 自己
> - `api.router` 仍保留為可單獨 import 的 APIRouter，未來要嵌入別的 service 也能 `from api import router`
>
> **排程 schema 收斂 (2026-05-28)**:`ScheduleCreateRequest` 拿掉 `minute` 和 `day_of_week` 兩個欄位(內部分別鎖死 `"0"` 和 `"*"`)；剩下的 `hour` / `day` / `month` 改成**必填**(原本預設 `"*"` 太容易誤觸成每小時跑)。排程精度只到「小時整點」,夠用且避免誤用。
>
> **`cat_id` 拉出來成 request 欄位 (2026-05-28)**:`ModuleCreateRequest` 多一個 `cat_id: int = 3`,會寫進 `PAYLOAD.CatID` 與 `gameEvt.CatID`(原本 hardcode 為 3)。PAYLOAD 的 shape 仍是籃球專用,只是為將來「per-sport 多模板」留下進入點(見 §8.3)。


### 8.1 已完成

**Core 層 (穩定，不需異動)**
- `client.py` / `config.py` / `main.py` / `settle.py` 完成，已在 module_18 等實際劇本跑過 (logs/run_module_18_*.log)
- `main.py` 已支援雙入口：CLI (`python main.py NN`) 與函式 (`run(plays, label, users_per_play)`)，per-run logger 用 `label + timestamp + 8 碼 run_id` 命名，並發跑不會互相污染
- 18 個資料模組 (`module_01.py ~ module_18.py`) + 4 份 CSV (`mbA~mbD`) 已就位

**API 整合層 `api/`**
- `__init__.py` — 對外只匯出 `router` (prefix=`/api/crontab`)，掛 `modules` + `schedules` 兩個子 router
- `schemas.py` — Pydantic v2 完整 schema (`PlayInput` / `ModuleCreateRequest` / `ModuleCreateResponse` / `ModuleSummary` / `ScheduleCreateRequest` / `ScheduleInfo`)
- `module_store.py` — `module_NN.py` 的 CRUD：render / write / list / get / delete；讀摘要用 `importlib.util.spec_from_file_location` 動態載入避開硬解析；`PAYLOAD_HALF/FULL` 用同一個 `_render_payload` 共享，只差 `settle_type` / `is_fh_finish` / `score_ext`
- `scheduler.py` — Linux crontab CRUD，`python-crontab` 套件；tag 用 `set-job:<8 碼 hex>`；`REPO_ROOT = Path.cwd()`、`PYTHON_BIN = sys.executable` 動態抓
- `routers/__init__.py` — 空 package marker (避免某些環境下 namespace package 解析失敗)
- `routers/modules.py` — `POST /modules` / `GET /modules` / `GET /modules/{n}` / `DELETE /modules/{n}`，409 / 404 錯誤處理已寫
- `routers/schedules.py` — `POST /schedules` / `GET /schedules` / `DELETE /schedules/{job_id}`，400 / 404 錯誤處理已寫

**其他**
- `requirements.txt`：`httpx>=0.27.0` / `requests>=2.33.1` / `fastapi>=0.110.0` / `pydantic>=2.0.0` / `python-crontab>=3.0.0`

### 8.2 接下來

1. **冒煙測試 (smoke test)** — 直接對 `app.py` 起來的 service 用 `TestClient` 跑：
   - `POST /api/crontab/modules` 建立一筆 → 驗 `module_NN.py` 內容能被 `main.run()` 讀
   - `POST /api/crontab/schedules` 建立一筆 → `GET /schedules` 看得到 → `DELETE` 後消失
2. **跨平台 scheduler** — `CronTab(user=True)` 在 Windows 上不存在；部署目標是 Linux，但開發機是 Windows。要不要加 `CRONTAB_FAKE_FILE` 環境變數讓 dev 走假檔 (`CronTab(tabfile=...)`)，production 仍走 `user=True` 真 crontab
3. **PAYLOAD schema 對齊驗證** — 把 `module_store.render_module_source()` 對某組固定輸入產出的 `PAYLOAD_HALF/FULL`，跟手寫的 `module_18.py` 結構 diff 一遍，確認沒漏欄位
4. **部署指引** — 補一段 Linux 部署步驟:`pip install -r requirements.txt` → `uvicorn app:app --host 0.0.0.0 --port 8022` → 透過 API 建立 crontab

### 8.3 未來再說 (列在 §5 改善空間，目前不阻擋整合)

- dry-run 模式 / 只重跑失敗清單 / 彙總報表
- 投注的指數退避重試
- 密碼抽 env (目前刻意維持渲染進 module_NN.py，因為帳密本身已是亂數)
- **per-sport 多模板**:目前 `PAYLOAD_HALF/FULL` 是籃球專用 shape(`FHHomeScore`、`FH = "x:y"` 等半場概念寫死)。要支援棒球 / 足球 / 網球需引入「per-sport renderer」,例如 `api/templates/{basketball,baseball,soccer}.py`,由 `cat_id` 或新加的 `sport` 欄位 dispatch。`cat_id` 已成 request 欄位即為這個方向預留的入口。