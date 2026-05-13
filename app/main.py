import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.api.routes import chat, orders, inventory, cargo
from app.api.routes import analytics, auth, customers, suppliers, invoices, marketplace
from app.api.routes import whatsapp
from pydantic import BaseModel
from app.core.config import settings
from app.db.database import engine, Base, get_session
from app.db import models  # registers ORM models with Base

logger = logging.getLogger(__name__)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")


def _migrate_columns():
    """Add new columns to existing tables without dropping data."""
    migrations = [
        "ALTER TABLE orders ADD COLUMN unit_price REAL DEFAULT 0.0",
        "ALTER TABLE orders ADD COLUMN customer_address TEXT",
        "ALTER TABLE orders ADD COLUMN notes TEXT",
        "ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'ödenmedi'",
        "ALTER TABLE orders ADD COLUMN payment_method TEXT",
        "ALTER TABLE orders ADD COLUMN payment_date DATETIME",
        "ALTER TABLE orders ADD COLUMN source TEXT DEFAULT 'manuel'",
        "ALTER TABLE inventory ADD COLUMN unit_price REAL DEFAULT 0.0",
        "ALTER TABLE inventory ADD COLUMN cost_price REAL DEFAULT 0.0",
        "ALTER TABLE inventory ADD COLUMN warehouse TEXT DEFAULT 'Ana Depo'",
        "ALTER TABLE inventory ADD COLUMN supplier_name TEXT",
        "ALTER TABLE cargo ADD COLUMN carrier TEXT",
        "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'owner'",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists


def _seed_database():
    """
    Demo verilerini takı mağazası senaryosuna göre tohumlar.
    ORD-128 varlığı kontrol edilir; yoksa eski veriler temizlenip yeni veriler eklenir.
    """
    db = get_session()
    try:
        JEWELRY_PRODUCTS = {
            "Güneş Kolyesi - Altın", "Güneş Kolyesi - Gümüş", "Zümrüt Taşlı Yüzük",
            "İnci Küpe", "Gümüş Bilezik", "Elmas Kolye", "Ay Kolye - Rose Gold", "Taşlı Bileklik",
        }

        # Takı dışı sipariş varsa tüm veriyi sıfırla
        non_jewelry = db.query(models.Order).filter(
            ~models.Order.product.in_(JEWELRY_PRODUCTS)
        ).count()
        jewelry_complete = db.query(models.Order).filter(models.Order.id == "ORD-128").count() > 0

        if jewelry_complete and non_jewelry == 0:
            db.close()
            return

        # Eski demo verilerini temizle (varsa)
        db.query(models.Order).delete()
        db.query(models.InventoryItem).delete()
        db.query(models.CargoRecord).delete()
        db.query(models.Customer).delete()
        db.query(models.Supplier).delete()
        db.commit()

        # ── Siparişler ──────────────────────────────────────────────────────
        db.add_all([
            models.Order(
                id="ORD-128", customer_name="Zeynep Arslan", customer_phone="05321234567",
                product="Güneş Kolyesi - Altın", quantity=1, unit_price=850.0,
                status="kargoda", created_at=datetime(2026, 5, 10, 11, 0),
                tracking_code="TRK-XYZ789",
                customer_address="Beşiktaş, İstanbul",
                notes="Hediye paketi istenildi",
            ),
            models.Order(
                id="ORD-129", customer_name="Ayşe Kaya", customer_phone="05001234567",
                product="Zümrüt Taşlı Yüzük", quantity=1, unit_price=1200.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 7, 9, 0),
                tracking_code="TRK-ABC123",
                customer_address="Kadıköy, İstanbul",
            ),
            models.Order(
                id="ORD-130", customer_name="Mehmet Demir", customer_phone="05329876543",
                product="Gümüş Bilezik", quantity=2, unit_price=380.0,
                status="beklemede", created_at=datetime(2026, 5, 13, 8, 30),
                tracking_code=None,
            ),
            models.Order(
                id="ORD-131", customer_name="Fatma Şahin", customer_phone="05441112233",
                product="İnci Küpe", quantity=1, unit_price=450.0,
                status="işlemde", created_at=datetime(2026, 5, 12, 14, 0),
                tracking_code=None,
                customer_address="Çankaya, Ankara",
            ),
            models.Order(
                id="ORD-132", customer_name="Ali Yıldız", customer_phone="05559990011",
                product="Elmas Kolye", quantity=1, unit_price=4500.0,
                status="kargoda", created_at=datetime(2026, 5, 9, 11, 0),
                tracking_code="TRK-DEF456",
                customer_address="Nilüfer, Bursa",
            ),
            # ── Mart-Nisan geçmişi (forecast analizi için 90 gün penceresi) ───
            models.Order(id="ORD-001", customer_name="Selin Yıldız", customer_phone="05301112233",
                product="İnci Küpe", quantity=3, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 2, 16, 10, 0), source="trendyol"),
            models.Order(id="ORD-002", customer_name="Hasan Öztürk", customer_phone="05422223344",
                product="Gümüş Bilezik", quantity=4, unit_price=380.0, status="teslim_edildi",
                created_at=datetime(2026, 2, 18, 14, 0), source="hepsiburada"),
            models.Order(id="ORD-003", customer_name="Burak Kara", customer_phone="05533334455",
                product="Güneş Kolyesi - Altın", quantity=2, unit_price=850.0, status="teslim_edildi",
                created_at=datetime(2026, 2, 21, 9, 0), source="manuel"),
            models.Order(id="ORD-004", customer_name="Merve Çelik", customer_phone="05644445566",
                product="İnci Küpe", quantity=2, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 2, 24, 11, 0), source="trendyol"),
            models.Order(id="ORD-005", customer_name="Emre Arslan", customer_phone="05755556677",
                product="Taşlı Bileklik", quantity=3, unit_price=280.0, status="teslim_edildi",
                created_at=datetime(2026, 2, 26, 16, 0), source="trendyol"),
            models.Order(id="ORD-006", customer_name="Elif Demir", customer_phone="05866667788",
                product="Gümüş Bilezik", quantity=3, unit_price=380.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 2, 10, 30), source="hepsiburada"),
            models.Order(id="ORD-007", customer_name="Can Şahin", customer_phone="05977778899",
                product="Zümrüt Taşlı Yüzük", quantity=2, unit_price=1200.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 5, 15, 0), source="manuel"),
            models.Order(id="ORD-008", customer_name="Zeynep Arslan", customer_phone="05321234567",
                product="İnci Küpe", quantity=4, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 8, 9, 0), source="trendyol"),
            models.Order(id="ORD-009", customer_name="Ayşe Kaya", customer_phone="05001234567",
                product="Güneş Kolyesi - Altın", quantity=2, unit_price=850.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 11, 14, 0), source="trendyol"),
            models.Order(id="ORD-010", customer_name="Fatma Şahin", customer_phone="05441112233",
                product="Taşlı Bileklik", quantity=4, unit_price=280.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 14, 10, 0), source="hepsiburada"),
            models.Order(id="ORD-011", customer_name="Ali Yıldız", customer_phone="05559990011",
                product="Gümüş Bilezik", quantity=3, unit_price=380.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 17, 11, 0), source="manuel"),
            models.Order(id="ORD-012", customer_name="Mehmet Demir", customer_phone="05329876543",
                product="İnci Küpe", quantity=3, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 20, 9, 0), source="trendyol"),
            models.Order(id="ORD-013", customer_name="Selin Yıldız", customer_phone="05301112233",
                product="Ay Kolye - Rose Gold", quantity=3, unit_price=720.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 23, 14, 0), source="trendyol"),
            models.Order(id="ORD-014", customer_name="Hasan Öztürk", customer_phone="05422223344",
                product="Zümrüt Taşlı Yüzük", quantity=2, unit_price=1200.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 26, 10, 0), source="hepsiburada"),
            models.Order(id="ORD-015", customer_name="Burak Kara", customer_phone="05533334455",
                product="Taşlı Bileklik", quantity=3, unit_price=280.0, status="teslim_edildi",
                created_at=datetime(2026, 3, 29, 9, 0), source="trendyol"),
            models.Order(id="ORD-016", customer_name="Merve Çelik", customer_phone="05644445566",
                product="İnci Küpe", quantity=3, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 2, 11, 0), source="trendyol"),
            models.Order(id="ORD-017", customer_name="Emre Arslan", customer_phone="05755556677",
                product="Gümüş Bilezik", quantity=4, unit_price=380.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 5, 16, 0), source="hepsiburada"),
            models.Order(id="ORD-018", customer_name="Elif Demir", customer_phone="05866667788",
                product="Güneş Kolyesi - Altın", quantity=3, unit_price=850.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 8, 10, 30), source="trendyol"),
            models.Order(id="ORD-019", customer_name="Can Şahin", customer_phone="05977778899",
                product="İnci Küpe", quantity=2, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 11, 15, 0), source="manuel"),
            models.Order(id="ORD-020", customer_name="Zeynep Arslan", customer_phone="05321234567",
                product="Ay Kolye - Rose Gold", quantity=3, unit_price=720.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 14, 9, 0), source="trendyol"),
            models.Order(id="ORD-021", customer_name="Ayşe Kaya", customer_phone="05001234567",
                product="Taşlı Bileklik", quantity=4, unit_price=280.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 17, 14, 0), source="hepsiburada"),
            models.Order(id="ORD-022", customer_name="Fatma Şahin", customer_phone="05441112233",
                product="Gümüş Bilezik", quantity=3, unit_price=380.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 20, 10, 0), source="trendyol"),
            models.Order(id="ORD-023", customer_name="Ali Yıldız", customer_phone="05559990011",
                product="Zümrüt Taşlı Yüzük", quantity=3, unit_price=1200.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 23, 11, 0), source="manuel"),
            models.Order(id="ORD-024", customer_name="Mehmet Demir", customer_phone="05329876543",
                product="İnci Küpe", quantity=3, unit_price=450.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 26, 9, 0), source="trendyol"),
            models.Order(id="ORD-025", customer_name="Selin Yıldız", customer_phone="05301112233",
                product="Güneş Kolyesi - Altın", quantity=2, unit_price=850.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 28, 14, 0), source="hepsiburada"),
            models.Order(id="ORD-026", customer_name="Hasan Öztürk", customer_phone="05422223344",
                product="Taşlı Bileklik", quantity=3, unit_price=280.0, status="teslim_edildi",
                created_at=datetime(2026, 4, 30, 10, 0), source="trendyol"),
            # ── Geçmiş haftalara yayılmış siparişler (analitik için) ──────────
            models.Order(
                id="ORD-110", customer_name="Selin Yıldız", customer_phone="05301112233",
                product="Güneş Kolyesi - Gümüş", quantity=2, unit_price=320.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 2, 10, 0),
                source="trendyol",
            ),
            models.Order(
                id="ORD-111", customer_name="Hasan Öztürk", customer_phone="05422223344",
                product="Ay Kolye - Rose Gold", quantity=1, unit_price=720.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 3, 14, 30),
                source="manuel",
            ),
            models.Order(
                id="ORD-112", customer_name="Burak Kara", customer_phone="05533334455",
                product="Taşlı Bileklik", quantity=3, unit_price=280.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 4, 9, 0),
                source="hepsiburada",
            ),
            models.Order(
                id="ORD-113", customer_name="Merve Çelik", customer_phone="05644445566",
                product="Zümrüt Taşlı Yüzük", quantity=1, unit_price=1200.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 5, 11, 0),
                source="trendyol",
            ),
            models.Order(
                id="ORD-114", customer_name="Emre Arslan", customer_phone="05755556677",
                product="Gümüş Bilezik", quantity=2, unit_price=380.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 6, 16, 0),
                source="manuel",
            ),
            models.Order(
                id="ORD-115", customer_name="Elif Demir", customer_phone="05866667788",
                product="İnci Küpe", quantity=2, unit_price=450.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 8, 10, 30),
                source="trendyol",
            ),
            models.Order(
                id="ORD-116", customer_name="Can Şahin", customer_phone="05977778899",
                product="Güneş Kolyesi - Altın", quantity=1, unit_price=850.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 8, 15, 0),
                source="hepsiburada",
            ),
            models.Order(
                id="ORD-120", customer_name="Zeynep Arslan", customer_phone="05321234567",
                product="Ay Kolye - Rose Gold", quantity=2, unit_price=720.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 11, 9, 0),
                source="trendyol",
            ),
            models.Order(
                id="ORD-121", customer_name="Ayşe Kaya", customer_phone="05001234567",
                product="Taşlı Bileklik", quantity=1, unit_price=280.0,
                status="teslim_edildi", created_at=datetime(2026, 5, 11, 14, 0),
                source="manuel",
            ),
            models.Order(
                id="ORD-122", customer_name="Fatma Şahin", customer_phone="05441112233",
                product="Zümrüt Taşlı Yüzük", quantity=1, unit_price=1200.0,
                status="kargoda", created_at=datetime(2026, 5, 12, 10, 0),
                source="trendyol", tracking_code="TRK-MNO111",
            ),
            models.Order(
                id="ORD-123", customer_name="Mehmet Demir", customer_phone="05329876543",
                product="İnci Küpe", quantity=1, unit_price=450.0,
                status="beklemede", created_at=datetime(2026, 5, 13, 7, 0),
                source="hepsiburada",
            ),
        ])

        # ── Stok (her ürün kendi kategori tedarikçisine bağlı) ──────────────
        db.add_all([
            # KATEGORİ: Kolye → Altın Atölye A.Ş.
            models.InventoryItem(
                product_name="Güneş Kolyesi - Altın", quantity=12, unit="adet",
                low_stock_threshold=5, unit_price=850.0, cost_price=480.0,
                supplier_email="tedarik@altinatölye.com", supplier_name="Altın Atölye A.Ş.",
                warehouse="Ana Depo",
            ),
            models.InventoryItem(
                product_name="Güneş Kolyesi - Gümüş", quantity=3, unit="adet",
                low_stock_threshold=5, unit_price=320.0, cost_price=160.0,
                supplier_email="tedarik@altinatölye.com", supplier_name="Altın Atölye A.Ş.",
                warehouse="Ana Depo",
            ),
            models.InventoryItem(
                product_name="Elmas Kolye", quantity=2, unit="adet",
                low_stock_threshold=3, unit_price=4500.0, cost_price=2800.0,
                supplier_email="tedarik@altinatölye.com", supplier_name="Altın Atölye A.Ş.",
                warehouse="Kasa",
            ),
            models.InventoryItem(
                product_name="Ay Kolye - Rose Gold", quantity=20, unit="adet",
                low_stock_threshold=5, unit_price=720.0, cost_price=390.0,
                supplier_email="tedarik@altinatölye.com", supplier_name="Altın Atölye A.Ş.",
                warehouse="Ana Depo",
            ),
            # KATEGORİ: Küpe & Yüzük → Taş Atölyesi Ltd.
            models.InventoryItem(
                product_name="İnci Küpe", quantity=8, unit="adet",
                low_stock_threshold=4, unit_price=450.0, cost_price=220.0,
                supplier_email="siparis@tasatölyesi.com", supplier_name="Taş Atölyesi Ltd.",
                warehouse="Ana Depo",
            ),
            models.InventoryItem(
                product_name="Zümrüt Taşlı Yüzük", quantity=7, unit="adet",
                low_stock_threshold=3, unit_price=1200.0, cost_price=680.0,
                supplier_email="siparis@tasatölyesi.com", supplier_name="Taş Atölyesi Ltd.",
                warehouse="Kasa",
            ),
            # KATEGORİ: Bileklik & Bilezik → Gümüş Dünyası San.
            models.InventoryItem(
                product_name="Gümüş Bilezik", quantity=15, unit="adet",
                low_stock_threshold=5, unit_price=380.0, cost_price=190.0,
                supplier_email="stok@gumusdünyasi.com", supplier_name="Gümüş Dünyası San.",
                warehouse="Ana Depo",
            ),
            models.InventoryItem(
                product_name="Taşlı Bileklik", quantity=5, unit="adet",
                low_stock_threshold=5, unit_price=280.0, cost_price=130.0,
                supplier_email="stok@gumusdünyasi.com", supplier_name="Gümüş Dünyası San.",
                warehouse="Ana Depo",
            ),
        ])

        # ── Kargo kayıtları ─────────────────────────────────────────────────
        db.add_all([
            models.CargoRecord(
                tracking_code="TRK-XYZ789", status="Dağıtımda",
                location="İstanbul Anadolu Dağıtım Merkezi",
                estimated_delivery="2026-05-14", last_update="2026-05-13T07:30:00",
                carrier="yurtici",
            ),
            models.CargoRecord(
                tracking_code="TRK-ABC123", status="Teslim Edildi",
                location="Kadıköy, İstanbul",
                estimated_delivery="2026-05-09", last_update="2026-05-09T15:20:00",
                carrier="yurtici",
            ),
            models.CargoRecord(
                tracking_code="TRK-DEF456", status="Dağıtımda",
                location="Bursa Dağıtım Merkezi",
                estimated_delivery="2026-05-14", last_update="2026-05-13T08:00:00",
                carrier="mng",
            ),
            models.CargoRecord(
                tracking_code="TRK-GHI999", status="Gecikti",
                location="İzmir Aktarma Merkezi",
                estimated_delivery="2026-05-13", last_update="2026-05-12T23:00:00",
                delay_reason="Yoğunluk nedeniyle aktarma gecikmesi",
                carrier="ptt",
            ),
        ])

        # ── Admin kullanıcısı ────────────────────────────────────────────────
        if db.query(models.User).count() == 0:
            from app.services.auth_service import hash_password
            db.add(models.User(
                email="admin@aura.ai",
                name="İşletme Sahibi",
                hashed_password=hash_password("aura2026"),
                role="owner",
            ))

        # ── Tedarikçiler (3 kategori) ────────────────────────────────────────
        db.add_all([
            models.Supplier(
                name="Altın Atölye A.Ş.", phone="02121234567",
                email="tedarik@altinatölye.com", address="Kapalıçarşı, İstanbul",
                product_categories="Kolye",
                payment_terms="30 gün vadeli",
                total_orders=24, total_spent=95000.0, rating=4.9,
                last_order_at=datetime(2026, 5, 1),
            ),
            models.Supplier(
                name="Taş Atölyesi Ltd.", phone="02161234567",
                email="siparis@tasatölyesi.com", address="Nişantaşı, İstanbul",
                product_categories="Küpe,Yüzük",
                payment_terms="Peşin + %5 indirim",
                total_orders=12, total_spent=142000.0, rating=5.0,
                last_order_at=datetime(2026, 5, 5),
            ),
            models.Supplier(
                name="Gümüş Dünyası San.", phone="02161234568",
                email="stok@gumusdünyasi.com", address="Bağcılar, İstanbul",
                product_categories="Bileklik,Bilezik",
                payment_terms="15 gün vadeli",
                total_orders=8, total_spent=48000.0, rating=4.7,
                last_order_at=datetime(2026, 5, 8),
            ),
        ])

        # ── Müşteriler ───────────────────────────────────────────────────────
        db.add_all([
            models.Customer(
                name="Zeynep Arslan", phone="05321234567",
                address="Beşiktaş, İstanbul",
                total_orders=3, total_spent=2350.0,
                last_order_at=datetime(2026, 5, 10),
            ),
            models.Customer(
                name="Ayşe Kaya", phone="05001234567", email="ayse@example.com",
                address="Kadıköy, İstanbul",
                total_orders=5, total_spent=4800.0,
                last_order_at=datetime(2026, 5, 7),
            ),
            models.Customer(
                name="Mehmet Demir", phone="05329876543",
                total_orders=2, total_spent=760.0,
                last_order_at=datetime(2026, 5, 13),
            ),
            models.Customer(
                name="Fatma Şahin", phone="05441112233",
                address="Çankaya, Ankara",
                total_orders=4, total_spent=3200.0,
                last_order_at=datetime(2026, 5, 12),
            ),
            models.Customer(
                name="Ali Yıldız", phone="05559990011", email="ali@example.com",
                address="Nilüfer, Bursa",
                total_orders=2, total_spent=5200.0,
                last_order_at=datetime(2026, 5, 9),
            ),
        ])

        db.commit()
        logger.info("Veritabanı takı mağazası demo verisiyle dolduruldu.")

    except Exception as exc:
        logger.error("Seed hatası: %s", exc)
        db.rollback()
    finally:
        db.close()


async def _proactive_monitor():
    """
    Arka plan görevi — kargo gecikmelerini ve kritik stokları periyodik olarak izler.

    Gecikmiş kargo veya kritik stok tespit edildiğinde yöneticiye WhatsApp mesajı gönderir.
    Aralık: settings.PROACTIVE_CHECK_INTERVAL (varsayılan 3600 saniye; demo için 60 ayarlayın).
    """
    from app.services.cargo_service import CargoService
    from app.services.inventory_service import InventoryService
    from app.services.notification_service import NotificationService
    from app.services.analytics_service import AnalyticsService

    cargo_svc = CargoService()
    inv_svc = InventoryService()
    notif = NotificationService()
    analytics_svc = AnalyticsService()

    await asyncio.sleep(10)  # Uygulama tam yüklenmeden önce küçük bekleme

    while True:
        try:
            admin = settings.ADMIN_PHONE
            if not admin or admin.startswith("+90XXXX"):
                await asyncio.sleep(settings.PROACTIVE_CHECK_INTERVAL)
                continue

            # Geciken kargolar
            delayed = cargo_svc.check_delayed()
            if delayed:
                lines = "\n".join(
                    f"• {c['tracking_code']} — {c['delay_reason'] or 'Sebep belirtilmemiş'}"
                    for c in delayed
                )
                await notif.send_whatsapp(
                    admin,
                    f"🚨 *Geciken Kargo Uyarısı*\n\n{lines}\n\n_Aura.AI | Otonom İzleme_",
                )
                logger.info("Proaktif: %d geciken kargo bildirimi gönderildi", len(delayed))

            # Kritik stok → admin WhatsApp + tedarikçiye kategori bazlı e-posta
            low_stock = inv_svc.get_low_stock()
            if low_stock:
                lines = "\n".join(
                    f"• {i['product']}: {i['quantity']} {i['unit']} kaldı"
                    for i in low_stock
                )
                await notif.send_whatsapp(
                    admin,
                    f"📉 *Kritik Stok Uyarısı*\n\n{lines}\n\n_Aura.AI | Stok İzleme_",
                )

                # Tedarikçiye e-posta — her tedarikçiye kendi ürünlerini toplu gönder
                supplier_items: dict[str, list] = {}
                for item in low_stock:
                    email = item.get("supplier_email") or ""
                    supplier_name = item.get("supplier_name") or "Tedarikçi"
                    if not email:
                        continue
                    if email not in supplier_items:
                        supplier_items[email] = {"name": supplier_name, "items": []}
                    supplier_items[email]["items"].append(item)

                for sup_email, sup_data in supplier_items.items():
                    product_lines_list = []
                    for i in sup_data["items"]:
                        velocity = analytics_svc.get_sales_velocity(i["product"], days=30)
                        last30 = velocity["total_sold"]
                        rec_qty = max(i["low_stock_threshold"] * 3, last30 * 2, 10)
                        line = (
                            f"  • {i['product']}: {i['quantity']} adet kaldı "
                            f"(eşik: {i['low_stock_threshold']}) | "
                            f"Son 30 gün satış: {last30} adet | Öneri: {rec_qty} adet sipariş"
                        )
                        product_lines_list.append(line)
                    product_lines = "\n".join(product_lines_list)
                    subject = f"[Aura.AI] Kritik Stok Bildirimi — {len(sup_data['items'])} ürün"
                    body = (
                        f"Sayın {sup_data['name']},\n\n"
                        f"Aşağıdaki ürünlerde stok kritik seviyeye düştü:\n\n"
                        f"{product_lines}\n\n"
                        f"📊 Sipariş miktarları sistem tarafından geçmiş satış verisi analiz edilerek önerilmiştir.\n\n"
                        f"En kısa sürede ikmal yapılmasını rica ederiz.\n\n"
                        f"Saygılarımızla,\nAura.AI Otonom Sipariş Sistemi"
                    )
                    result = notif.send_email(sup_email, subject, body)
                    logger.info(
                        "Tedarikçi maili: %s → %s (%s)",
                        sup_data["name"], sup_email,
                        "OK" if result.get("success") else result.get("error", "hata"),
                    )

                logger.info("Proaktif: %d kritik stok, %d tedarikçiye mail gönderildi",
                            len(low_stock), len(supplier_items))

        except Exception as exc:
            logger.error("Proaktif izleme hatası: %s", exc)

        await asyncio.sleep(settings.PROACTIVE_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    _seed_database()
    # Proaktif izleme görevini arka planda başlat
    monitor_task = asyncio.create_task(_proactive_monitor())
    logger.info("Proaktif izleme görevi başlatıldı (aralık: %ss)", settings.PROACTIVE_CHECK_INTERVAL)
    yield
    monitor_task.cancel()  # Uygulama kapanırken görevi durdur


app = FastAPI(
    title="Aura.AI — Otonom Takı Mağazası Asistanı",
    description="Butik takı mağazaları için WhatsApp entegrasyonlu otonom yapay zeka asistanı",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(orders.router, prefix="/api/orders", tags=["Siparişler"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Stok"])
app.include_router(cargo.router, prefix="/api/cargo", tags=["Kargo"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analitik"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(customers.router, prefix="/api/customers", tags=["Müşteriler"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Tedarikçiler"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Faturalar"])
app.include_router(marketplace.router, prefix="/api/marketplace", tags=["Marketplace"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_ui():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/demo")
async def serve_demo():
    return FileResponse(os.path.join(STATIC_DIR, "demo.html"))


# ── Demo endpoint'leri (iki aktörlü mimari) ───────────────────────────────────

_demo_conversations: dict[str, list[dict]] = {}


class _CustomerMsg(BaseModel):
    phone: str = "+905321234567"
    message: str


@app.post(
    "/api/demo/message",
    tags=["Demo"],
    summary="Aktör 1 — Müşteri WhatsApp mesajı gönder",
    description=(
        "Müşterinin WhatsApp'tan mesaj attığı anı simüle eder.\n\n"
        "Ajan niyeti analiz eder → veritabanını sorgular → doğal Türkçe yanıt üretir.\n\n"
        "**Test mesajları:**\n"
        "- `128 numaralı siparişim ne zaman gelir?`\n"
        "- `Güneş kolyenin gümüş rengi stokta var mı?`\n"
        "- `İade politikanız nedir?`"
    ),
)
async def demo_customer_message(body: _CustomerMsg):
    from app.agents.kobi_agent import KOBIAgent
    from fastapi import HTTPException
    from google.genai.errors import ClientError, ServerError
    agent = KOBIAgent()
    history = list(_demo_conversations.get(body.phone, []))
    _demo_conversations.setdefault(body.phone, []).append(
        {"role": "user", "content": body.message}
    )
    try:
        reply, tools_used = await agent.chat(body.message, history)
    except (ClientError, ServerError) as e:
        code = getattr(e, "status_code", 0) or 0
        if code == 429 or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(status_code=429, detail="Gemini API kota limiti doldu. Lütfen 1-2 dakika bekleyin.")
        if code == 503 or "503" in str(e) or "UNAVAILABLE" in str(e):
            raise HTTPException(status_code=503, detail="Gemini API şu an yoğun, lütfen birkaç saniye sonra tekrar deneyin.")
        raise HTTPException(status_code=502, detail=f"Gemini API hatası: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent hatası: {str(e)[:200]}")
    _demo_conversations[body.phone].append({"role": "model", "content": reply})
    return {
        "phone": body.phone,
        "customer_message": body.message,
        "agent_reply": reply,
        "tools_used": tools_used,
        "actor": "Aktör 1 — Müşteri",
        "agent": "Aura.AI (Gemini Flash + Function Calling + RAG)",
    }


@app.delete("/api/demo/conversation/{phone}", tags=["Demo"], summary="Konuşma geçmişini sıfırla")
async def demo_reset(phone: str):
    _demo_conversations.pop(phone.replace("%2B", "+"), None)
    return {"status": "cleared"}


@app.get("/api/demo/scenarios", tags=["Demo"], summary="Hazır demo senaryoları")
async def demo_scenarios():
    return {"scenarios": [
        {"id": 1, "title": "Kargo Takibi",     "message": "128 numaralı siparişim ne zaman gelir?"},
        {"id": 2, "title": "Stok Sorgulama",   "message": "Güneş kolyenin gümüş rengi stokta var mı?"},
        {"id": 3, "title": "İade Politikası",  "message": "İade politikanız nedir?"},
        {"id": 4, "title": "Sipariş Ver",       "message": "Zümrüt taşlı yüzükten bir adet almak istiyorum, adım Ayşe Yılmaz"},
    ]}


@app.get("/health")
async def health():
    return {"status": "healthy"}
