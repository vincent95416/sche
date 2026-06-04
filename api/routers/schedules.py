"""
/schedules — Linux crontab CRUD,只動有 "calc-job:" tag 的行。
"""
from fastapi import APIRouter, HTTPException

from ..schemas import ScheduleCreateRequest, ScheduleInfo
from ..scheduler import create_schedule, delete_schedule, list_schedules

router = APIRouter(prefix="/schedules", tags=["settlement-schedules"])


@router.post("", response_model=ScheduleInfo, status_code=201)
def add_schedule(req: ScheduleCreateRequest) -> ScheduleInfo:
    try:
        return create_schedule(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[ScheduleInfo])
def list_all_schedules() -> list[ScheduleInfo]:
    return list_schedules()


@router.delete("/{job_id}", status_code=204)
def delete_one_schedule(job_id: str) -> None:
    if not delete_schedule(job_id):
        raise HTTPException(status_code=404, detail=f"job_id 不存在: {job_id}")