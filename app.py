"""
settle service — 獨立 FastAPI app 入口。

啟動(從 settlement 根目錄):
    uvicorn app:app --host 0.0.0.0 --port 8022

掛載的 router 維持模組化,需要時也可以單獨 import:
    from api import router as settle_router
"""
from fastapi import FastAPI
from api import router as settle_router

app = FastAPI(title="下注&結算排程-service", version="0.1.0")
app.include_router(settle_router)

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}