import math
from datetime import datetime, timedelta
from sqlalchemy import func
from app.db.database import get_session
from app.db import models


class AnalyticsService:
    def get_summary(self) -> dict:
        db = get_session()
        try:
            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

            all_orders = db.query(models.Order).all()
            delivered = [o for o in all_orders if o.status == "teslim_edildi"]
            monthly = [o for o in all_orders if o.created_at and o.created_at >= month_start]
            weekly = [o for o in all_orders if o.created_at and o.created_at >= week_start]

            def revenue(orders):
                total = 0.0
                for o in orders:
                    price = o.unit_price or 0.0
                    total += price * o.quantity
                return round(total, 2)

            monthly_rev = revenue(monthly)
            weekly_rev = revenue(weekly)
            total_rev = revenue(delivered)

            avg_order = round(total_rev / len(delivered), 2) if delivered else 0.0

            # Top 5 products by order count
            product_counts: dict[str, dict] = {}
            for o in all_orders:
                if o.product not in product_counts:
                    product_counts[o.product] = {"product": o.product, "count": 0, "revenue": 0.0}
                product_counts[o.product]["count"] += o.quantity
                product_counts[o.product]["revenue"] += (o.unit_price or 0.0) * o.quantity

            top_products = sorted(product_counts.values(), key=lambda x: x["count"], reverse=True)[:5]
            for p in top_products:
                p["revenue"] = round(p["revenue"], 2)

            # Orders by status
            status_counts = {}
            for o in all_orders:
                status_counts[o.status] = status_counts.get(o.status, 0) + 1

            # Inventory health
            inventory = db.query(models.InventoryItem).all()
            critical_count = sum(1 for i in inventory if i.quantity <= i.low_stock_threshold)
            inventory_value = sum(
                (i.unit_price or 0.0) * i.quantity for i in inventory
            )

            # Payment stats
            paid_orders = [o for o in all_orders if getattr(o, "payment_status", None) == "ödendi"]
            unpaid_orders = [o for o in all_orders if getattr(o, "payment_status", "ödenmedi") != "ödendi"]
            paid_revenue = revenue(paid_orders)
            unpaid_revenue = revenue(unpaid_orders)

            # Profit margin (kâr marjı)
            total_cost = sum((i.cost_price or 0.0) * i.quantity for i in inventory)
            gross_profit = round(inventory_value - total_cost, 2)
            margin_pct = round(gross_profit / inventory_value * 100, 1) if inventory_value > 0 else 0.0

            # Warehouse distribution
            warehouse_dist: dict[str, int] = {}
            for i in inventory:
                wh = getattr(i, "warehouse", "Ana Depo") or "Ana Depo"
                warehouse_dist[wh] = warehouse_dist.get(wh, 0) + 1

            # Source/platform stats
            source_dist: dict[str, dict] = {}
            for o in all_orders:
                src = getattr(o, "source", "manuel") or "manuel"
                if src not in source_dist:
                    source_dist[src] = {"platform": src, "count": 0, "revenue": 0.0}
                source_dist[src]["count"] += 1
                source_dist[src]["revenue"] += (o.unit_price or 0.0) * o.quantity
            for p in source_dist.values():
                p["revenue"] = round(p["revenue"], 2)

            # Cargo stats
            cargo_all = db.query(models.CargoRecord).all()
            cargo_status = {}
            for c in cargo_all:
                cargo_status[c.status] = cargo_status.get(c.status, 0) + 1

            return {
                "orders": {
                    "total": len(all_orders),
                    "monthly": len(monthly),
                    "weekly": len(weekly),
                    "by_status": status_counts,
                },
                "revenue": {
                    "total_delivered": total_rev,
                    "monthly": monthly_rev,
                    "weekly": weekly_rev,
                    "avg_order_value": avg_order,
                    "paid": paid_revenue,
                    "unpaid": unpaid_revenue,
                    "paid_count": len(paid_orders),
                    "unpaid_count": len(unpaid_orders),
                },
                "top_products": top_products,
                "inventory": {
                    "total_items": len(inventory),
                    "critical_count": critical_count,
                    "total_value": round(inventory_value, 2),
                    "total_cost": round(total_cost, 2),
                    "gross_profit": gross_profit,
                    "margin_pct": margin_pct,
                    "by_warehouse": warehouse_dist,
                },
                "cargo": {
                    "total": len(cargo_all),
                    "by_status": cargo_status,
                },
                "platforms": list(source_dist.values()),
                "generated_at": now.isoformat(),
            }
        finally:
            db.close()

    def get_sales_velocity(self, product_name: str, days: int = 30) -> dict:
        """Son N günde ürün satış hızı."""
        db = get_session()
        try:
            cutoff = datetime.now() - timedelta(days=days)
            orders = db.query(models.Order).filter(
                models.Order.product == product_name,
                models.Order.created_at >= cutoff,
                models.Order.status != "iptal",
            ).all()
            total_sold = sum(o.quantity for o in orders)
            return {
                "product": product_name,
                "days": days,
                "total_sold": total_sold,
                "daily_avg": round(total_sold / days, 2),
            }
        finally:
            db.close()

    def get_forecast(self) -> dict:
        """Son 90 gün satış verisinden önümüzdeki hafta top 5 ürün tahmini."""
        db = get_session()
        try:
            cutoff = datetime.now() - timedelta(days=90)
            all_orders = db.query(models.Order).filter(
                models.Order.created_at >= cutoff,
                models.Order.status != "iptal",
            ).all()

            products: dict[str, dict] = {}
            for o in all_orders:
                if o.product not in products:
                    products[o.product] = {
                        "product": o.product,
                        "total_sold_90d": 0,
                        "revenue_90d": 0.0,
                    }
                products[o.product]["total_sold_90d"] += o.quantity
                products[o.product]["revenue_90d"] += (o.unit_price or 0.0) * o.quantity

            for p in products.values():
                p["weekly_velocity"] = round(p["total_sold_90d"] / 13, 1)
                p["predicted_next_week"] = max(1, math.ceil(p["weekly_velocity"]))
                p["revenue_90d"] = round(p["revenue_90d"], 2)

            top5 = sorted(products.values(), key=lambda x: x["weekly_velocity"], reverse=True)[:5]

            inventory = {i.product_name: i.quantity for i in db.query(models.InventoryItem).all()}
            for p in top5:
                stock = inventory.get(p["product"], 0)
                p["current_stock"] = stock
                p["stock_warning"] = stock <= p["weekly_velocity"] * 2

            return {
                "top5_forecast": top5,
                "period_days": 90,
                "generated_at": datetime.now().isoformat(),
            }
        finally:
            db.close()
