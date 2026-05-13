from app.db.database import get_session
from app.db.models import InventoryItem as InventoryModel


def _to_dict(item: InventoryModel) -> dict:
    unit_price = item.unit_price or 0.0
    cost_price = getattr(item, "cost_price", 0.0) or 0.0
    margin_pct = round((unit_price - cost_price) / unit_price * 100, 1) if unit_price > 0 else 0.0
    return {
        "product": item.product_name,
        "quantity": item.quantity,
        "unit": item.unit,
        "low_stock_threshold": item.low_stock_threshold,
        "supplier_email": item.supplier_email,
        "supplier_name": getattr(item, "supplier_name", None),
        "unit_price": unit_price,
        "cost_price": cost_price,
        "margin_pct": margin_pct,
        "stock_value": round(unit_price * item.quantity, 2),
        "warehouse": getattr(item, "warehouse", "Ana Depo") or "Ana Depo",
        "kritik_stok": item.quantity <= item.low_stock_threshold,
    }


class InventoryService:
    def get_status(self, product_name: str = None) -> dict | list:
        db = get_session()
        try:
            if product_name:
                item = db.get(InventoryModel, product_name)
                if not item:
                    return {"error": f"Ürün bulunamadı: {product_name}"}
                return _to_dict(item)
            return [_to_dict(i) for i in db.query(InventoryModel).all()]
        finally:
            db.close()

    def get_low_stock(self) -> list:
        db = get_session()
        try:
            items = db.query(InventoryModel).all()
            return [_to_dict(i) for i in items if i.quantity <= i.low_stock_threshold]
        finally:
            db.close()

    def update_stock(self, product_name: str, quantity: int) -> dict:
        db = get_session()
        try:
            item = db.get(InventoryModel, product_name)
            if not item:
                return {"error": f"Ürün bulunamadı: {product_name}"}
            item.quantity = quantity
            db.commit()
            result = _to_dict(item)
            result["updated"] = True
            return result
        finally:
            db.close()

    def decrease_stock(self, product_name: str, amount: int) -> dict:
        """Stoktan belirtilen miktarı düşer. Negatife inmez."""
        db = get_session()
        try:
            item = db.get(InventoryModel, product_name)
            if not item:
                return {"error": f"Ürün bulunamadı: {product_name}"}
            item.quantity = max(0, item.quantity - amount)
            db.commit()
            result = _to_dict(item)
            result["decreased_by"] = amount
            return result
        finally:
            db.close()

    def list_all(self) -> list:
        db = get_session()
        try:
            return [_to_dict(i) for i in db.query(InventoryModel).all()]
        finally:
            db.close()

    def list_by_warehouse(self, warehouse: str) -> list:
        db = get_session()
        try:
            items = db.query(InventoryModel).filter(
                InventoryModel.warehouse == warehouse
            ).all()
            return [_to_dict(i) for i in items]
        finally:
            db.close()

    def get_warehouses(self) -> list:
        db = get_session()
        try:
            items = db.query(InventoryModel).all()
            warehouses = {}
            for i in items:
                wh = getattr(i, "warehouse", "Ana Depo") or "Ana Depo"
                if wh not in warehouses:
                    warehouses[wh] = {"warehouse": wh, "item_count": 0, "total_value": 0.0}
                warehouses[wh]["item_count"] += 1
                warehouses[wh]["total_value"] += (i.unit_price or 0.0) * i.quantity
            for wh in warehouses.values():
                wh["total_value"] = round(wh["total_value"], 2)
            return list(warehouses.values())
        finally:
            db.close()

    def add_item(self, product_name: str, quantity: int, unit: str,
                 low_stock_threshold: int, supplier_email: str = None,
                 unit_price: float = 0.0, cost_price: float = 0.0,
                 warehouse: str = "Ana Depo", supplier_name: str = None) -> dict:
        db = get_session()
        try:
            if db.get(InventoryModel, product_name):
                return {"error": f"Bu ürün zaten mevcut: {product_name}"}
            item = InventoryModel(
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                low_stock_threshold=low_stock_threshold,
                supplier_email=supplier_email,
                unit_price=unit_price,
                cost_price=cost_price,
                warehouse=warehouse,
                supplier_name=supplier_name,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return _to_dict(item)
        finally:
            db.close()
