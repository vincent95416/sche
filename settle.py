"""
結算主程式

用法 (CLI,從 settlement 根目錄):
    python settle.py 1     # 跑 module_01 的結算
    python settle.py 2
    ...

用法 (webservice / 其他 Python 程式碼):
    from settle import run
    run(admin_username="...", admin_password="...",
        payload_half={...}, payload_full={...},
        event_id="25844225", label="adhoc-001")

讀的是同一份 module_XX,跟 main.py 共用,
因為投注和結算是同一場賽事,屬於同一天的劇本。

流程:
  登入 (cookie 認證)
    ↓
  打 PAYLOAD_HALF → 檢查 result==1 (獨立判讀,失敗也繼續)
    ↓
  打 PAYLOAD_FULL → 檢查 result==1 (獨立判讀)
"""
import sys
import uuid
import logging
import importlib
from datetime import datetime

from client import SettlementClient
from config import LOG_DIR


def _build_logger(label: str) -> logging.Logger:
    # per-run 獨立 logger,並發跑多個 run 時 log 不互相污染
    run_id = uuid.uuid4().hex[:8]
    log_file = LOG_DIR / f"settle_{label}_{datetime.now():%Y%m%d_%H%M%S}_{run_id}.log"

    logger = logging.getLogger(f"settle.{label}.{run_id}")
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


def call_settlement(client: SettlementClient, stage_name: str,
                    payload: dict, log: logging.Logger) -> bool:
    """打一次結算,獨立判讀 result==1。回傳 True/False"""
    log.info(f"--- {stage_name} 開始 ---")
    try:
        resp = client.settle(payload)
    except Exception as e:
        log.error(f"{stage_name} 呼叫例外: {e}")
        return False

    if resp.get("result") == 1:
        log.info(f"{stage_name} 成功 ✓ | resp={resp}")
        return True
    else:
        log.error(f"{stage_name} 失敗 ✗ | resp={resp}")
        return False


def run(admin_username: str, admin_password: str,
        payload_half: dict, payload_full: dict,
        label: str, event_id: str = "") -> None:
    """
    結算主入口 (webservice / CLI 共用)

    Args:
        admin_username / admin_password: 結算後台帳密
        payload_half / payload_full: 半場 / 全場 結算 payload
        label: 本次 run 的識別字串(CLI: "module_03";webservice: 自訂 label)
        event_id: 賽事 ID,只用於 log 訊息
    """
    log = _build_logger(label)
    log.info(f"####### 結算腳本啟動 ({label}) #######")
    if event_id:
        log.info(f"目標賽事: {event_id}")

    client = SettlementClient()
    try:
        log.info("登入中...")
        client.login(admin_username, admin_password)
        log.info("登入成功")

        half_ok = call_settlement(client, "半場結算", payload_half, log)
        full_ok = call_settlement(client, "全場結算", payload_full, log)

        log.info(f"結算結束 | 半場={'OK' if half_ok else 'FAIL'}, "
                 f"全場={'OK' if full_ok else 'FAIL'}")
    finally:
        client.close()
    log.info(f"####### 結算腳本結束 ({label}) #######")


def _parse_module_arg() -> int:
    if len(sys.argv) < 2:
        print("用法: python settle.py <module_number>")
        sys.exit(1)
    try:
        n = int(sys.argv[1])
    except ValueError:
        print(f"module 編號必須是整數,收到: {sys.argv[1]}")
        sys.exit(1)
    if n < 1 or n > 4:
        print(f"module 編號必須介於 1~4,收到: {n}")
        sys.exit(1)
    return n


def _cli_entry():
    module_num = _parse_module_arg()
    data_module = importlib.import_module(f"module.module_{module_num:02d}")
    run(
        admin_username=data_module.ADMIN_USERNAME,
        admin_password=data_module.ADMIN_PASSWORD,
        payload_half=data_module.PAYLOAD_HALF,
        payload_full=data_module.PAYLOAD_FULL,
        label=f"module_{module_num:02d}",
        event_id=data_module.EVENT_ID,
    )


if __name__ == "__main__":
    _cli_entry()