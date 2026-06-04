"""
投注主程式

用法 (CLI,從 settlement 根目錄):
    python main.py 1     # 跑 module_01
    python main.py 2     # 跑 module_02
    ...

用法 (webservice / 其他 Python 程式碼):
    from main import run
    run(plays=[{"csv_file": "mbA.csv", "cat_id": 3,
                "wager_string": "...", "amount": 100}, ...],
        label="adhoc-001")

流程:
  for 玩法 in PLAYS:
      讀對應 csv,取前 USERS_PER_PLAY 個帳號
      for user in 帳號:
          登入 → sleep 2s → 投注 → sleep 2s → 下一位
"""
import csv
import sys
import time
import uuid
import logging
import importlib
from datetime import datetime
from client import BettingClient
from config import CSV_DIR, DEFAULT_PASSWORD, \
    SLEEP_AFTER_LOGIN, SLEEP_AFTER_BET, LOG_DIR


def _build_logger(label: str) -> logging.Logger:
    # per-run 獨立 logger,並發跑多個 run 時 log 不互相污染
    run_id = uuid.uuid4().hex[:8]
    log_file = LOG_DIR / f"run_{label}_{datetime.now():%Y%m%d_%H%M%S}_{run_id}.log"

    logger = logging.getLogger(f"bet.{label}.{run_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

def load_usernames(csv_filename: str, limit: int) -> list[str]:
    """
    讀 csv,取前 limit 個帳號(只有一欄,無 header)
    用 utf-8-sig 處理 BOM,並清掉所有空白類字元(空格/tab/換行/全形空白等)
    """
    path = CSV_DIR / csv_filename
    usernames = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            raw = str(row[0])
            cleaned = "".join(ch for ch in raw if not ch.isspace())
            if cleaned:
                usernames.append(cleaned)
    return usernames[:limit]


def run_play(client: BettingClient, play: dict, play_index: int,
             limit: int, log: logging.Logger):
    csv_file = play["csv_file"]
    cat_id = play["cat_id"]
    wager = play["wager_string"]
    amount = play["amount"]

    log.info(f"===== 玩法 {play_index} 開始 (csv={csv_file}, 取前 {limit} 人) =====")

    usernames = load_usernames(csv_file, limit)
    log.info(f"載入 {len(usernames)} 個帳號")

    success = 0
    failed = 0
    failed_users = []

    for i, username in enumerate(usernames, start=1):
        try:
            session = client.login(username, DEFAULT_PASSWORD)
            log.info(f"[{play_index}] ({i}/{len(usernames)}) 登入成功: {username}")

            time.sleep(SLEEP_AFTER_LOGIN)

            result = client.place_bet(
                session=session,
                cat_id=cat_id,
                wager_string=wager,
                amount=amount,
            )
            log.info(f"[{play_index}] ({i}/{len(usernames)}) 投注完成: {username} | resp={result}")
            success += 1

            time.sleep(SLEEP_AFTER_BET)

        except Exception as e:
            failed += 1
            failed_users.append((username, str(e)))
            log.error(f"[{play_index}] ({i}/{len(usernames)}) 失敗: {username} | err={e}")
            continue

    if failed_users:
        fail_file = LOG_DIR / f"failed_play{play_index}_{datetime.now():%Y%m%d_%H%M%S}.csv"
        with open(fail_file, "w", encoding="utf-8") as f:
            f.write("username,error\n")
            for u, err in failed_users:
                safe_err = str(err).replace(",", ";").replace("\n", " ")
                f.write(f"{u},{safe_err}\n")
        log.info(f"失敗帳號清單: {fail_file}")

    log.info(f"===== 玩法 {play_index} 結束 (成功={success}, 失敗={failed}) =====\n")


def run(plays: list[dict], label: str,
        users_per_play: int = 1) -> None:
    """
    投注主入口 (webservice / CLI 共用)

    Args:
        plays: 玩法清單,每個 dict 需含 csv_file / cat_id / wager_string / amount
        label: 本次 run 的識別字串(CLI: "module_03";webservice: 自訂 label)
        users_per_play: 每個玩法跑前幾位 user;CLI 會從 module.USERS_PER_PLAY 帶入
    """
    limit = users_per_play
    log = _build_logger(label)
    log.info(f"####### 投注腳本啟動 ({label},每玩法 {limit} 人) #######")
    client = BettingClient()
    try:
        for idx, play in enumerate(plays, start=1):
            run_play(client, play, idx, limit, log)
    finally:
        client.close()
    log.info(f"####### 投注腳本結束 ({label}) #######")


def _parse_module_arg() -> int:
    if len(sys.argv) < 2:
        print("用法: python main.py <module_number>")
        sys.exit(1)
    try:
        return int(sys.argv[1])
    except ValueError:
        print(f"module 編號必須是整數,收到: {sys.argv[1]}")
        sys.exit(1)


def _cli_entry():
    module_num = _parse_module_arg()
    data_module = importlib.import_module(f"module.module_{module_num:02d}")
    run(
        data_module.PLAYS,
        label=f"module_{module_num:02d}",
        users_per_play=getattr(data_module, "USERS_PER_PLAY", 1),
    )


if __name__ == "__main__":
    _cli_entry()