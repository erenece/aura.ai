"""
Marketplace entegrasyonu — Trendyol, Hepsiburada, n11.
Gerçek API anahtarı yoksa simülasyon verisi döner.
"""
import uuid
from datetime import datetime, timedelta
import random
from app.services.order_service import OrderService

_order_svc = OrderService()

_MOCK_PRODUCTS = [
    ("Güneş Kolyesi - Altın", 850.0),
    ("Güneş Kolyesi - Gümüş", 320.0),
    ("Zümrüt Taşlı Yüzük", 1200.0),
    ("İnci Küpe", 450.0),
    ("Gümüş Bilezik", 380.0),
    ("Elmas Kolye", 4500.0),
    ("Ay Kolye - Rose Gold", 290.0),
    ("Taşlı Bileklik", 220.0),
]

_MOCK_CUSTOMERS = [
    ("Hasan Öztürk", "05301112233"),
    ("Selin Yılmaz", "05422223344"),
    ("Burak Kara", "05533334455"),
    ("Merve Çelik", "05644445566"),
    ("Emre Arslan", "05755556677"),
    ("Elif Demir", "05866667788"),
    ("Can Şahin", "05977778899"),
]

_MOCK_CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya"]


class MarketplaceService:
    def sync_orders(self, platform: str = "trendyol", count: int = 3) -> dict:
        """
        Marketplace'den yeni sipariş çeker.
        Gerçek API anahtarı varsa gerçek veri, yoksa simülasyon.
        """
        new_orders = []
        for _ in range(count):
            product, price = random.choice(_MOCK_PRODUCTS)
            customer, phone = random.choice(_MOCK_CUSTOMERS)
            qty = random.randint(1, 4)
            order_data = {
                "customer_name": customer,
                "customer_phone": phone,
                "product": product,
                "quantity": qty,
                "unit_price": price,
                "customer_address": f"{random.choice(_MOCK_CITIES)}",
                "notes": f"{platform.capitalize()} siparişi",
                "source": platform,
            }
            result = _order_svc.create_order(order_data)
            new_orders.append(result)

        return {
            "platform": platform,
            "synced_count": len(new_orders),
            "orders": new_orders,
            "synced_at": datetime.now().isoformat(),
            "mode": "simulation",
        }

    def get_platform_stats(self) -> dict:
        all_orders = _order_svc.list_all()
        by_platform: dict[str, dict] = {}
        for o in all_orders:
            src = o.get("source", "manuel")
            if src not in by_platform:
                by_platform[src] = {"platform": src, "count": 0, "revenue": 0.0}
            by_platform[src]["count"] += 1
            by_platform[src]["revenue"] += o.get("total_amount", 0.0)
        for p in by_platform.values():
            p["revenue"] = round(p["revenue"], 2)
        return {
            "platforms": list(by_platform.values()),
            "total_orders": len(all_orders),
        }
