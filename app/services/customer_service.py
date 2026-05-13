from datetime import datetime
from typing import Optional
from app.db.database import get_session
from app.db import models


def _to_dict(c: models.Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "address": c.address,
        "notes": c.notes,
        "total_orders": c.total_orders,
        "total_spent": round(c.total_spent or 0.0, 2),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "last_order_at": c.last_order_at.isoformat() if c.last_order_at else None,
    }


class CustomerService:
    def list_all(self, search: str = None) -> list:
        db = get_session()
        try:
            q = db.query(models.Customer)
            if search:
                term = f"%{search}%"
                q = q.filter(
                    models.Customer.name.ilike(term) |
                    models.Customer.phone.ilike(term) |
                    models.Customer.email.ilike(term)
                )
            return [_to_dict(c) for c in q.order_by(models.Customer.total_spent.desc()).all()]
        finally:
            db.close()

    def get(self, customer_id: int) -> dict:
        db = get_session()
        try:
            c = db.get(models.Customer, customer_id)
            if not c:
                return {"error": f"Müşteri bulunamadı: {customer_id}"}
            return _to_dict(c)
        finally:
            db.close()

    def find_or_create(self, name: str, phone: str = None, email: str = None, address: str = None) -> dict:
        """Müşteri adı veya telefonu ile ara, yoksa oluştur."""
        db = get_session()
        try:
            existing = None
            if phone:
                existing = db.query(models.Customer).filter(models.Customer.phone == phone).first()
            if not existing and email:
                existing = db.query(models.Customer).filter(models.Customer.email == email).first()

            if existing:
                return _to_dict(existing)

            c = models.Customer(name=name, phone=phone, email=email, address=address)
            db.add(c)
            db.commit()
            db.refresh(c)
            return _to_dict(c)
        finally:
            db.close()

    def create(self, name: str, phone: str = None, email: str = None,
                address: str = None, notes: str = None) -> dict:
        db = get_session()
        try:
            c = models.Customer(name=name, phone=phone, email=email, address=address, notes=notes)
            db.add(c)
            db.commit()
            db.refresh(c)
            return _to_dict(c)
        finally:
            db.close()

    def update(self, customer_id: int, **kwargs) -> dict:
        db = get_session()
        try:
            c = db.get(models.Customer, customer_id)
            if not c:
                return {"error": f"Müşteri bulunamadı: {customer_id}"}
            for k, v in kwargs.items():
                if v is not None and hasattr(c, k):
                    setattr(c, k, v)
            db.commit()
            db.refresh(c)
            return _to_dict(c)
        finally:
            db.close()

    def record_order(self, customer_id: int, order_amount: float) -> dict:
        """Sipariş tamamlandığında müşteri istatistiklerini güncelle."""
        db = get_session()
        try:
            c = db.get(models.Customer, customer_id)
            if not c:
                return {"error": "Müşteri bulunamadı"}
            c.total_orders = (c.total_orders or 0) + 1
            c.total_spent = (c.total_spent or 0.0) + order_amount
            c.last_order_at = datetime.now()
            db.commit()
            db.refresh(c)
            return _to_dict(c)
        finally:
            db.close()

    def get_orders(self, customer_id: int) -> list:
        """Müşterinin tüm siparişlerini getir (telefon veya isim eşleşmesi)."""
        db = get_session()
        try:
            c = db.get(models.Customer, customer_id)
            if not c:
                return []
            orders = db.query(models.Order).filter(
                (models.Order.customer_phone == c.phone) |
                (models.Order.customer_name == c.name)
            ).order_by(models.Order.created_at.desc()).all()

            from app.services.order_service import _to_dict as order_dict
            return [order_dict(o) for o in orders]
        finally:
            db.close()

    def delete(self, customer_id: int) -> dict:
        db = get_session()
        try:
            c = db.get(models.Customer, customer_id)
            if not c:
                return {"error": f"Müşteri bulunamadı: {customer_id}"}
            db.delete(c)
            db.commit()
            return {"deleted": True, "id": customer_id}
        finally:
            db.close()

    def get_stats(self) -> dict:
        db = get_session()
        try:
            customers = db.query(models.Customer).all()
            total = len(customers)
            active = sum(1 for c in customers if c.total_orders > 0)
            top = sorted(customers, key=lambda c: c.total_spent or 0, reverse=True)[:5]
            return {
                "total": total,
                "active": active,
                "top_customers": [_to_dict(c) for c in top],
            }
        finally:
            db.close()
