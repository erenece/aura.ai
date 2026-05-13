from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import CargoCreate
from app.services.cargo_service import CargoService
from app.services.cargo_api_service import CargoAPIService
from app.services.notification_service import NotificationService

router = APIRouter()
service = CargoService()
cargo_api = CargoAPIService()
notif = NotificationService()


@router.get("/")
def list_all_cargo(status: Optional[str] = Query(None)):
    return service.list_all(status)


@router.get("/delayed")
def delayed_cargo():
    items = service.check_delayed()
    return {"geciken_kargolar": items, "toplam": len(items)}


@router.get("/track/{tracking_code}")
async def track_cargo(tracking_code: str):
    """Önce DB'ye bakar, yoksa kargo API'siyle sorgular."""
    result = await cargo_api.track_shipment(tracking_code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/")
def add_cargo(data: CargoCreate):
    result = service.add_cargo(
        data.tracking_code, data.status, data.location,
        data.estimated_delivery, data.delay_reason,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/carrier-sync")
async def carrier_sync():
    """Kargo firması API simülasyonu — aktif kargoları rastgele günceller ve müşterileri bilgilendirir."""
    result = service.simulate_carrier_update()
    notifications = []
    for upd in result.get("updated", []):
        phone = upd.get("customer_phone")
        name = upd.get("customer_name")
        if not phone or phone.startswith("+90XXXX"):
            continue
        notif_result = await notif.notify_cargo_update(
            phone=phone,
            customer_name=name,
            tracking_code=upd["tracking_code"],
            new_status=upd["new_status"],
            location=upd["location"],
        )
        notifications.append({
            "tracking_code": upd["tracking_code"],
            "customer_name": name,
            "new_status": upd["new_status"],
            "sent": notif_result.get("success", False),
            "channel": notif_result.get("servis", "whatsapp"),
        })
    result["notifications"] = notifications
    return result


@router.patch("/{tracking_code}/status")
def update_cargo_status(tracking_code: str, status: str, location: Optional[str] = None):
    """Kargo firmasından durum güncellemesi — Teslim Edildi ise siparişi de kapatır."""
    valid = {"Yolda", "Dağıtımda", "Teslim Edildi", "Gecikti"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Geçersiz durum. Seçenekler: {valid}")
    result = service.update_status(tracking_code, status, location)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/restock-email")
def restock_email(product_name: str, quantity_needed: int):
    """Tedarikçi e-postası gönderir (SMTP yapılandırıldıysa gerçekten gider)."""
    return service.draft_restock_email(product_name, quantity_needed)


@router.post("/notify-customer")
async def notify_customer(
    phone: str,
    customer_name: str,
    order_id: str,
    product: str,
    status: str,
    tracking_code: Optional[str] = None,
):
    """Müşteriye WhatsApp ile sipariş durumu bildirimi gönderir."""
    return await notif.notify_order_status(phone, customer_name, order_id, product, status, tracking_code)


@router.post("/send-message")
async def send_custom_message(phone: str, message: str):
    """Belirtilen telefona serbest metin WhatsApp mesajı gönderir."""
    return await notif.send_whatsapp(phone, message)
