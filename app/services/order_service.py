from datetime import datetime
from typing import Optional
import uuid
from app.db.database import get_session
from app.db.models import Order as OrderModel


def _to_dict(order: OrderModel) -> dict:
    unit_price = order.unit_price or 0.0
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "product": order.product,
        "quantity": order.quantity,
        "unit_price": unit_price,
        "total_amount": round(unit_price * order.quantity, 2),
        "status": order.status,
        "payment_status": getattr(order, "payment_status", "ödenmedi") or "ödenmedi",
        "payment_method": getattr(order, "payment_method", None),
        "payment_date": order.payment_date.isoformat() if getattr(order, "payment_date", None) else None,
        "source": getattr(order, "source", "manuel") or "manuel",
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "tracking_code": order.tracking_code,
        "customer_address": order.customer_address,
        "notes": order.notes,
    }


class OrderService:
    def get_order(self, order_id: str) -> dict:
        db = get_session()
        try:
            order = db.get(OrderModel, order_id.upper())
            if not order:
                return {"error": f"Sipariş bulunamadı: {order_id}"}
            return _to_dict(order)
        finally:
            db.close()

    def list_pending(self) -> list:
        db = get_session()
        try:
            orders = db.query(OrderModel).filter(
                OrderModel.status.in_(["beklemede", "işlemde"])
            ).all()
            return [_to_dict(o) for o in orders]
        finally:
            db.close()

    def create_order(self, data: dict) -> dict:
        db = get_session()
        try:
            order_id = f"ORD-{str(uuid.uuid4())[:6].upper()}"
            order = OrderModel(
                id=order_id,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                product=data["product"],
                quantity=data["quantity"],
                unit_price=data.get("unit_price", 0.0),
                status="beklemede",
                created_at=datetime.now(),
                tracking_code=None,
                customer_address=data.get("customer_address"),
                notes=data.get("notes"),
                source=data.get("source", "manuel"),
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            return _to_dict(order)
        finally:
            db.close()

    def update_payment(self, order_id: str, payment_status: str, payment_method: Optional[str] = None) -> dict:
        db = get_session()
        try:
            order = db.get(OrderModel, order_id.upper())
            if not order:
                return {"error": f"Sipariş bulunamadı: {order_id}"}
            order.payment_status = payment_status
            if payment_method:
                order.payment_method = payment_method
            if payment_status == "ödendi":
                order.payment_date = datetime.now()
            db.commit()
            db.refresh(order)
            return _to_dict(order)
        finally:
            db.close()

    def update_status(self, order_id: str, status: str, tracking_code: Optional[str] = None) -> dict:
        db = get_session()
        try:
            order = db.get(OrderModel, order_id.upper())
            if not order:
                return {"error": f"Sipariş bulunamadı: {order_id}"}
            order.status = status
            if tracking_code:
                order.tracking_code = tracking_code
            db.commit()
            db.refresh(order)
            return _to_dict(order)
        finally:
            db.close()

    def list_all(self) -> list:
        db = get_session()
        try:
            orders = db.query(OrderModel).order_by(OrderModel.created_at.desc()).all()
            return [_to_dict(o) for o in orders]
        finally:
            db.close()
