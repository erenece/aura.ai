from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean
from datetime import datetime
from app.db.database import Base


class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    product = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=True, default=0.0)
    status = Column(String, default="beklemede")
    payment_status = Column(String, default="ödenmedi")   # ödenmedi | ödendi | kısmi
    payment_method = Column(String, nullable=True)        # nakit | kredi_karti | havale | eft
    payment_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    tracking_code = Column(String, nullable=True)
    customer_address = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    source = Column(String, default="manuel")             # manuel | trendyol | hepsiburada


class InventoryItem(Base):
    __tablename__ = "inventory"
    product_name = Column(String, primary_key=True)
    quantity = Column(Integer, nullable=False)
    unit = Column(String, nullable=False)
    low_stock_threshold = Column(Integer, nullable=False)
    supplier_email = Column(String, nullable=True)
    unit_price = Column(Float, nullable=True, default=0.0)
    cost_price = Column(Float, nullable=True, default=0.0)  # alış fiyatı (kâr marjı için)
    warehouse = Column(String, nullable=True, default="Ana Depo")  # depo/raf konumu
    supplier_name = Column(String, nullable=True)           # tedarikçi adı (FK yerine basit string)


class CargoRecord(Base):
    __tablename__ = "cargo"
    tracking_code = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    location = Column(String, nullable=False)
    estimated_delivery = Column(String, nullable=False)
    last_update = Column(String, nullable=False)
    delay_reason = Column(String, nullable=True)
    carrier = Column(String, nullable=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="owner")  # owner | staff | accountant
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    product_categories = Column(String, nullable=True)  # virgülle ayrılmış kategoriler
    payment_terms = Column(String, nullable=True)       # örn: "30 gün vadeli"
    notes = Column(String, nullable=True)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    rating = Column(Float, default=5.0)                 # 1-5 yıldız
    created_at = Column(DateTime, default=datetime.now)
    last_order_at = Column(DateTime, nullable=True)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    last_order_at = Column(DateTime, nullable=True)
