"""
/modules — 建立 / 列出 / 查詢 / 刪除 settlement/module/module_NN.py。
"""
from fastapi import APIRouter, HTTPException

from ..schemas import (
    ModuleCreateRequest,
    ModuleCreateResponse,
    ModuleSummary,
)
from ..module_store import (
    delete_module,
    get_module,
    list_modules,
    write_module_file,
)

router = APIRouter(prefix="/modules", tags=["settlement-modules"])


@router.post("", response_model=ModuleCreateResponse, status_code=201)
def create_module(req: ModuleCreateRequest) -> ModuleCreateResponse:
    try:
        path, existed = write_module_file(req)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ModuleCreateResponse(
        module_number=req.module_number,
        path=str(path),
        overwritten=existed,
    )


@router.get("", response_model=list[ModuleSummary])
def list_all_modules() -> list[ModuleSummary]:
    return list_modules()


@router.get("/{n}", response_model=ModuleSummary)
def get_one_module(n: int) -> ModuleSummary:
    try:
        return get_module(n)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{n}", status_code=204)
def delete_one_module(n: int) -> None:
    if not delete_module(n):
        raise HTTPException(status_code=404, detail=f"module_{n:02d}.py 不存在")