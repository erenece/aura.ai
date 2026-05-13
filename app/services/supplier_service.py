from datetime import datetime
from app.db.database import get_session
from app.db.models import Supplier as SupplierModel


def _to_dict(s: SupplierModel) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "phone": s.phone,
        "email": s.email,
        "address": s.address,
        "product_categories": s.product_categories,
        "payment_terms": s.payment_terms,
        "notes": s.notes,
        "total_orders": s.total_orders or 0,
        "total_spent": round(s.total_spent or 0.0, 2),
        "rating": s.rating or 5.0,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "last_order_at": s.last_order_at.isoformat() if s.last_order_at else None,
    }


class SupplierService:
    def list_all(self, search: str = None) -> list:
        db = get_session()
        try:
            q = db.query(SupplierModel)
            if search:
                q = q.filter(SupplierModel.name.ilike(f"%{search}%"))
            return [_to_dict(s) for s in q.order_by(SupplierModel.name).all()]
        finally:
            db.close()

    def get(self, supplier_id: int) -> dict:
        db = get_session()
        try:
            s = db.get(SupplierModel, supplier_id)
            if not s:
                return {"error": f"Tedarikçi bulunamadı: {supplier_id}"}
            return _to_dict(s)
        finally:
            db.close()

    def create(self, data: dict) -> dict:
        db = get_session()
        try:
            s = SupplierModel(
                name=data["name"],
                phone=data.get("phone"),
                email=data.get("email"),
                address=data.get("address"),
                product_categories=data.get("product_categories"),
                payment_terms=data.get("payment_terms"),
                notes=data.get("notes"),
                rating=data.get("rating", 5.0),
                created_at=datetime.now(),
            )
            db.add(s)
            db.commit()
            db.refresh(s)
            return _to_dict(s)
        finally:
            db.close()

    def update(self, supplier_id: int, data: dict) -> dict:
        db = get_session()
        try:
            s = db.get(SupplierModel, supplier_id)
            if not s:
                return {"error": f"Tedarikçi bulunamadı: {supplier_id}"}
            for field in ("phone", "email", "address", "product_categories", "payment_terms", "notes", "rating"):
                if field in data and data[field] is not None:
                    setattr(s, field, data[field])
            db.commit()
            db.refresh(s)
            return _to_dict(s)
        finally:
            db.close()

    def delete(self, supplier_id: int) -> dict:
        db = get_session()
        try:
            s = db.get(SupplierModel, supplier_id)
            if not s:
                return {"error": f"Tedarikçi bulunamadı: {supplier_id}"}
            db.delete(s)
            db.commit()
            return {"deleted": True, "id": supplier_id}
        finally:
            db.close()

    def record_order(self, supplier_id: int, amount: float) -> dict:
        db = get_session()
        try:
            s = db.get(SupplierModel, supplier_id)
            if not s:
                return {"error": f"Tedarikçi bulunamadı: {supplier_id}"}
            s.total_orders = (s.total_orders or 0) + 1
            s.total_spent = (s.total_spent or 0.0) + amount
            s.last_order_at = datetime.now()
            db.commit()
            return _to_dict(s)
        finally:
            db.close()

    def get_stats(self) -> dict:
        db = get_session()
        try:
            suppliers = db.query(SupplierModel).all()
            total_spent = sum(s.total_spent or 0.0 for s in suppliers)
            return {
                "total_suppliers": len(suppliers),
                "total_spent": round(total_spent, 2),
                "avg_rating": round(
                    sum(s.rating or 5.0 for s in suppliers) / len(suppliers), 1
                ) if suppliers else 0.0,
            }
        finally:
            db.close()
