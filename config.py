"""
共用設定
"""
from pathlib import Path

# CSV 資料夾路徑
CSV_DIR = Path(__file__).parent / "csv_data"

# 固定密碼
DEFAULT_PASSWORD = "v1_\\WH|P}T4"

# 每個動作之間的等待秒數
SLEEP_AFTER_LOGIN = 2.0
SLEEP_AFTER_BET = 2.0

# log 檔輸出位置
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
