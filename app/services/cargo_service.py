import random
from datetime import datetime
from app.db.database import get_session
from app.db.models import CargoRecord as CargoModel, InventoryItem as InventoryModel
from app.services.notification_service import NotificationService

_notif = NotificationService()


def _to_dict(c: CargoModel) -> dict:
    return {
        "tracking_code": c.tracking_code,
        "status": c.status,
        "location": c.location,
        "estimated_delivery": c.estimated_delivery,
        "last_update": c.last_update,
        "delay_reason": c.delay_reason,
        "carrier": getattr(c, "carrier", None),
    }


class CargoService:
    def track(self, tracking_code: str) -> dict:
        db = get_session()
        try:
            record = db.get(CargoModel, tracking_code.upper())
            if not record:
                return {"error": f"Kargo takip kodu bulunamadı: {tracking_code}"}
            return _to_dict(record)
        finally:
            db.close()

    def draft_restock_email(self, product_name: str, quantity_needed: int) -> dict:
        """Tedarikçi e-postası hazırlar ve SMTP yapılandırıldıysa gerçekten gönderir."""
        db = get_session()
        try:
            item = db.get(InventoryModel, product_name)
            supplier_email = item.supplier_email if item else None
        finally:
            db.close()

        if supplier_email:
            result = _notif.send_restock_email(product_name, quantity_needed, supplier_email)
            result["gonderildi"] = result.get("success", False)
            return result

        # Tedarikçi e-postası yoksa sadece taslak döndür
        body = f"""Sayın Tedarikçi,

Mağazamızda {product_name} stoğu kritik seviyeye düşmüştür.
{quantity_needed} adet/kg acil sipariş vermek istiyoruz.

Lütfen en kısa sürede stok durumunuzu ve teslimat tarihinizi bildirin.

Saygılarımızla,
Aura.AI"""
        return {
            "konu": f"Acil Stok Talebi — {product_name}",
            "icerik": body,
            "urun": product_name,
            "miktar": quantity_needed,
            "gonderildi": False,
            "uyari": "Tedarikçi e-posta adresi kayıtlı değil",
        }

    def simulate_carrier_update(self) -> dict:
        """
        Kargo firması API'sini simüle eder.
        Aktif kargoların durumunu rastgele ilerletir.
        """
        db = get_session()
        try:
            records = db.query(CargoModel).filter(
                CargoModel.status != "Teslim Edildi"
            ).all()

            _locations = {
                "Yolda":       ["Gönderici Deposu", "Aktarma Merkezi", "İstanbul HUB", "Ankara Dağıtım"],
                "Dağıtımda":   ["Dağıtım Aracında", "Mahalle Dağıtım Noktası", "Son Mil Aracında"],
                "Teslim Edildi": ["Teslim Noktası", "Müşteri Adresi"],
            }

            _next = {"Yolda": "Dağıtımda", "Dağıtımda": "Teslim Edildi", "Gecikti": "Yolda"}

            updates = []
            orders_delivered = []

            for rec in records:
                # %75 ihtimalle güncelleme gelsin
                if random.random() > 0.75:
                    continue
                new_status = _next.get(rec.status, "Yolda")
                new_location = random.choice(_locations.get(new_status, ["Kargo Merkezi"]))
                rec.status = new_status
                rec.location = new_location
                rec.last_update = datetime.now().isoformat()
                from app.db.models import Order as OrderModel
                linked_order = db.query(OrderModel).filter(
                    OrderModel.tracking_code == rec.tracking_code
                ).first()
                update_entry = {
                    "tracking_code": rec.tracking_code,
                    "old_status": _next.get(new_status, rec.status),
                    "new_status": new_status,
                    "location": new_location,
                    "customer_phone": linked_order.customer_phone if linked_order else None,
                    "customer_name": linked_order.customer_name if linked_order else None,
                    "order_id": linked_order.id if linked_order else None,
                    "product": linked_order.product if linked_order else None,
                }
                updates.append(update_entry)
                if new_status == "Teslim Edildi":
                    if linked_order and linked_order.status != "teslim_edildi":
                        linked_order.status = "teslim_edildi"
                        orders_delivered.append(rec.tracking_code)

            db.commit()
            return {
                "updated": updates,
                "total_checked": len(records),
                "total_updated": len(updates),
                "orders_delivered": orders_delivered,
            }
        finally:
            db.close()

    def check_delayed(self) -> list:
        db = get_session()
        try:
            records = db.query(CargoModel).filter(CargoModel.status == "Gecikti").all()
            return [_to_dict(r) for r in records]
        finally:
            db.close()

    def list_all(self, status: str = None) -> list:
        db = get_session()
        try:
            query = db.query(CargoModel)
            if status:
                query = query.filter(CargoModel.status == status)
            records = query.order_by(CargoModel.last_update.desc()).all()
            return [_to_dict(r) for r in records]
        finally:
            db.close()

    def update_status(self, tracking_code: str, new_status: str, location: str = None) -> dict:
        """Kargo durumunu günceller. Teslim Edildi ise ilgili siparişi de kapatır."""
        db = get_session()
        try:
            record = db.get(CargoModel, tracking_code.upper())
            if not record:
                return {"error": f"Kargo bulunamadı: {tracking_code}"}
            record.status = new_status
            record.last_update = datetime.now().isoformat()
            if location:
                record.location = location
            # Teslim edildi → ilgili siparişi kapat
            order_updated = False
            if new_status == "Teslim Edildi":
                from app.db.models import Order as OrderModel
                order = db.query(OrderModel).filter(
                    OrderModel.tracking_code == tracking_code.upper()
                ).first()
                if order and order.status != "teslim_edildi":
                    order.status = "teslim_edildi"
                    order_updated = True
            db.commit()
            result = _to_dict(record)
            result["order_updated"] = order_updated
            return result
        finally:
            db.close()

    def add_cargo(self, tracking_code: str, status: str, location: str, estimated_delivery: str, delay_reason: str = None) -> dict:
        db = get_session()
        try:
            code = tracking_code.upper()
            if db.get(CargoModel, code):
                return {"error": f"Bu takip kodu zaten mevcut: {tracking_code}"}
            record = CargoModel(
                tracking_code=code,
                status=status,
                location=location,
                estimated_delivery=estimated_delivery,
                last_update=datetime.now().isoformat(),
                delay_reason=delay_reason,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return _to_dict(record)
        finally:
            db.close()
