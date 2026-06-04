"""
Linux crontab CRUD,透過 python-crontab 套件操作目前 user 的 crontab。

排程觸發時實際執行的命令 (REPO_ROOT 即 settlement 根目錄):
    cd <repo_root> && <python> main.py   <NN> >> logs/cron.log 2>&1
    cd <repo_root> && <python> settle.py <NN> >> logs/cron.log 2>&1
"""
from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path
from typing import Optional

from crontab import CronTab

from .schemas import JobKind, ScheduleCreateRequest, ScheduleInfo

# settlement 根目錄 — 直接用 cwd (預期從 settlement 根目錄起 service)
REPO_ROOT = Path.cwd()
PYTHON_BIN = sys.executable  # 跑 FastAPI 的這支 python,確保跟 webservice 用同一個環境

TAG_PREFIX = "set-job:"
_CMD_RE = re.compile(r"\b(main|settle)\.py\s+(\d+)")


def _new_job_id() -> str:
    return uuid.uuid4().hex[:8]


def _build_command(kind: JobKind, module_number: int) -> str:
    script = "main.py" if kind == "bet" else "settle.py"
    log_path = REPO_ROOT / "logs" / "cron.log"
    return (
        f"cd {REPO_ROOT} && "
        f"{PYTHON_BIN} {script} {module_number} "
        f">> {log_path} 2>&1"
    )


def _parse_command(command: str) -> tuple[Optional[JobKind], Optional[int]]:
    m = _CMD_RE.search(command)
    if not m:
        return None, None
    kind: JobKind = "bet" if m.group(1) == "main" else "settle"
    return kind, int(m.group(2))


def create_schedule(req: ScheduleCreateRequest) -> ScheduleInfo:
    cron = CronTab(user=True)
    job_id = req.job_id or _new_job_id()

    tag = f"{TAG_PREFIX}{job_id}"
    if any(j.comment == tag for j in cron):
        raise ValueError(f"job_id 已存在: {job_id}")

    command = _build_command(req.kind, req.module_number)
    job = cron.new(command=command, comment=tag)
    # minute 固定 "0" + day_of_week 固定 "*" — 精度鎖到小時整點,只用具體日期排程
    cron_expr = f"0 {req.hour} {req.day} {req.month} *"
    try:
        job.setall(cron_expr)
    except Exception as e:
        raise ValueError(f"cron 表示式不合法: {cron_expr} ({e})")
    if not job.is_valid():
        raise ValueError(f"cron 表示式不合法: {cron_expr}")

    cron.write()
    return ScheduleInfo(
        job_id=job_id,
        kind=req.kind,
        module_number=req.module_number,
        cron_expr=cron_expr,
        command=command,
    )


def list_schedules() -> list[ScheduleInfo]:
    cron = CronTab(user=True)
    results: list[ScheduleInfo] = []
    for job in cron:
        comment = job.comment or ""
        if not comment.startswith(TAG_PREFIX):
            continue
        job_id = comment[len(TAG_PREFIX):]
        kind, module_number = _parse_command(str(job.command))
        if kind is None or module_number is None:
            # 命令被外部改過,認不出來;跳過
            continue
        results.append(ScheduleInfo(
            job_id=job_id,
            kind=kind,
            module_number=module_number,
            cron_expr=str(job.slices),
            command=str(job.command),
        ))
    return results


def delete_schedule(job_id: str) -> bool:
    cron = CronTab(user=True)
    removed = cron.remove_all(comment=f"{TAG_PREFIX}{job_id}")
    if removed:
        cron.write()
    return removed > 0
