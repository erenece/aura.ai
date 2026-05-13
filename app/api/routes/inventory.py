import asyncio
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import InventoryItemCreate
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.core.config import settings

router = APIRouter()
service = InventoryService()
notif = NotificationService()


@router.get("/")
def list_inventory():
    return service.list_all()


@router.get("/low-stock")
def low_stock_alert():
    items = service.get_low_stock()
    return {"kritik_urunler": items, "toplam": len(items)}


@router.get("/warehouses")
def list_warehouses():
    return service.get_warehouses()


@router.post("/")
def add_inventory_item(data: InventoryItemCreate):
    result = service.add_item(
        data.product_name, data.quantity, data.unit,
        data.low_stock_threshold, data.supplier_email,
        getattr(data, 'unit_price', 0.0) or 0.0,
        getattr(data, 'cost_price', 0.0) or 0.0,
        getattr(data, 'warehouse', 'Ana Depo') or 'Ana Depo',
        getattr(data, 'supplier_name', None),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{product_name}")
def get_product(product_name: str):
    result = service.get_status(product_name)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.patch("/{product_name}/decrease")
async def decrease_stock(product_name: str, amount: int = Query(..., ge=1)):
    result = service.decrease_stock(product_name, amount)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    if result.get("kritik_stok") and settings.ADMIN_PHONE and not settings.ADMIN_PHONE.startswith("+90XXXX"):
        asyncio.create_task(
            notif.notify_low_stock(settings.ADMIN_PHONE, product_name, result["quantity"], result.get("unit", "adet"))
        )
    return result


@router.patch("/{product_name}/stock")
async def update_stock(product_name: str, quantity: int):
    result = service.update_stock(product_name, quantity)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Kritik seviyenin altına düştüyse admin telefonuna WhatsApp at
    if result.get("kritik_stok") and settings.CALLMEBOT_PHONE:
        asyncio.create_task(
            notif.notify_low_stock(
                settings.CALLMEBOT_PHONE,
                product_name,
                quantity,
                result.get("unit", "adet"),
            )
        )

    return result
