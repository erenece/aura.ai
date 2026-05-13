from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.services.customer_service import CustomerService

router = APIRouter()
service = CustomerService()


class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
def list_customers(search: Optional[str] = Query(None)):
    return service.list_all(search=search)


@router.get("/stats")
def customer_stats():
    return service.get_stats()


@router.get("/{customer_id}")
def get_customer(customer_id: int):
    result = service.get(customer_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{customer_id}/orders")
def get_customer_orders(customer_id: int):
    return service.get_orders(customer_id)


@router.post("/")
def create_customer(data: CustomerCreate):
    return service.create(data.name, data.phone, data.email, data.address, data.notes)


@router.patch("/{customer_id}")
def update_customer(customer_id: int, data: CustomerUpdate):
    result = service.update(customer_id, **data.model_dump(exclude_none=True))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/{customer_id}")
def delete_customer(customer_id: int):
    result = service.delete(customer_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
