"""
api — FastAPI 整合層。

對外只匯出一個 router (prefix=/api/crontab),底下掛 modules / schedules 兩個子 router。

同 service 內接線方式 (見 app.py):

    from api import router as settle_router
    app.include_router(settle_router)

路由總覽:
    POST   /api/crontab/modules               建立 / 覆寫 module_NN.py
    GET    /api/crontab/modules               列出所有 module 摘要
    GET    /api/crontab/modules/{n}           單一 module 摘要
    DELETE /api/crontab/modules/{n}           刪除 module_NN.py

    POST   /api/crontab/schedules             新增 crontab 排程
    GET    /api/crontab/schedules             列出我們管理的 crontab
    DELETE /api/crontab/schedules/{job_id}    刪除指定 crontab
"""
from fastapi import APIRouter

from .routers.modules import router as _modules_router
from .routers.schedules import router as _schedules_router

router = APIRouter(prefix="/api/crontab")
router.include_router(_modules_router)
router.include_router(_schedules_router)

__all__ = ["router"]