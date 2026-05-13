from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models.schemas import SupplierCreate, SupplierUpdate
from app.services.supplier_service import SupplierService

router = APIRouter()
service = SupplierService()


@router.get("/")
def list_suppliers(search: Optional[str] = Query(None)):
    return service.list_all(search)


@router.get("/stats")
def supplier_stats():
    return service.get_stats()


@router.get("/{supplier_id}")
def get_supplier(supplier_id: int):
    result = service.get(supplier_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/")
def create_supplier(data: SupplierCreate):
    return service.create(data.model_dump())


@router.patch("/{supplier_id}")
def update_supplier(supplier_id: int, data: SupplierUpdate):
    result = service.update(supplier_id, data.model_dump(exclude_none=True))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int):
    result = service.delete(supplier_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{supplier_id}/record-order")
def record_order(supplier_id: int, amount: float):
    result = service.record_order(supplier_id, amount)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
