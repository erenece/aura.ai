import asyncio
from fastapi import APIRouter, HTTPException
from app.models.schemas import OrderCreate, OrderStatusUpdate, PaymentStatusUpdate
from app.services.order_service import OrderService
from app.services.notification_service import NotificationService

router = APIRouter()
service = OrderService()
notif = NotificationService()


@router.get("/")
def list_orders():
    return service.list_all()


@router.get("/pending")
def pending_orders():
    return service.list_pending()


@router.get("/{order_id}")
def get_order(order_id: str):
    result = service.get_order(order_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.patch("/{order_id}/payment")
def update_payment(order_id: str, update: PaymentStatusUpdate):
    result = service.update_payment(order_id, update.payment_status, update.payment_method)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/")
def create_order(data: OrderCreate):
    return service.create_order(data.model_dump())


@router.patch("/{order_id}/status")
async def update_order_status(order_id: str, update: OrderStatusUpdate):
    result = service.update_status(order_id, update.status, update.tracking_code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Sipariş sahibine WhatsApp bildirimi gönder (arka planda, hata olursa sessiz geç)
    phone = result.get("customer_phone")
    name = result.get("customer_name")
    if phone and name:
        asyncio.create_task(
            notif.notify_order_status(
                phone, name, order_id,
                result.get("product", ""),
                update.status,
                update.tracking_code,
            )
        )

    return result
