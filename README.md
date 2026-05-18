

https://github.com/user-attachments/assets/347995d6-4134-4240-99e6-129667732718


# Aura.AI — Otonom Takı Mağazası Asistanı

> **YZTA 5.0 Hackathon** — "Otonom Yapay Zeka Ajanları" kategorisi

Günde 50+ sipariş alan butik takı mağazaları için tasarlanmış, WhatsApp entegrasyonlu, RAG tabanlı otonom operasyon asistanı. Sipariş yönetimi, stok takibi, kargo izleme ve müşteri iletişimi tek bir sistemde.

---

## Sistem Mimarisi

```
┌──────────────────────────────────────────────────────────────────────┐
│                        AURA.AI SİSTEM MİMARİSİ                      │
└──────────────────────────────────────────────────────────────────────┘

  KULLANICI KANALLARI                    YÖNETİM PANELI (Web UI)
  ──────────────────                     ──────────────────────────
  WhatsApp Müşteri                       Tarayıcı (index.html)
       │                                       │
       ▼                                       ▼
  /api/whatsapp/webhook              /api/chat  ← → Gemini
  (Twilio / Meta Business)           (web chat)

                    ┌─────────────────────────────────────┐
                    │           KOBIAgent                 │
                    │   Google Gemini 2.5 Flash           │
                    │   + Function Calling (13 araç)      │
                    │   + Konuşma Geçmişi (bellek-içi)   │
                    └───────────────┬─────────────────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               ▼                    ▼                     ▼
        RAGService           OrderService          CargoService
    (Gemini Embeddings     (Sipariş CRUD)       (Kargo Takip +
     + Keyword fallback)                        Carrier Sync)
               ▼                    ▼                     ▼
        product_catalog.json    SQLite DB            SQLite DB
                                                          │
                                                          ▼
                                                   CargoAPIService
                                                (Yurtiçi/MNG/PTT/Aras
                                                  mock + gerçek API)

  SERVIS KATMANI (Tüm İş Mantığı)
  ─────────────────────────────────
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │InventoryServ │  │ AnalyticsSrv │  │CustomerServ  │  │SupplierServ  │
  │ (Stok CRUD)  │  │(Özet+Tahmin) │  │ (Müşteri DB) │  │(Tedarikçi DB)│
  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │                   NotificationService                            │
  │  E-posta: Resend API → SMTP (Gmail) fallback                    │
  │  WhatsApp: Twilio → Meta Business API → CallMeBot fallback      │
  └──────────────────────────────────────────────────────────────────┘

  PROAKTİF İZLEME (asyncio arka plan görevi)
  ────────────────────────────────────────────
  Her N dakikada bir (PROACTIVE_CHECK_INTERVAL):
  ① Geciken kargolar  →  Admin WhatsApp
  ② Kritik stok       →  Admin WhatsApp + Tedarikçiye e-posta
     (son 30 gün satış analizi ile akıllı sipariş miktarı hesabı)

  VERİTABANI (SQLite + SQLAlchemy ORM)
  ──────────────────────────────────────
  ┌──────────┐  ┌──────────────┐  ┌─────────────┐
  │  orders  │  │  inventory   │  │    cargo    │
  └──────────┘  └──────────────┘  └─────────────┘
  ┌──────────┐  ┌──────────────┐  ┌─────────────┐
  │  users   │  │  customers   │  │  suppliers  │
  └──────────┘  └──────────────┘  └─────────────┘

  AUTH
  ────
  JWT (HS256, 24 saat)  +  PBKDF2-SHA256 şifre hash
```

---

## Özellikler

### Otonom Yapay Zeka Ajanı
- Google Gemini 2.5 Flash ile doğal dil anlama
- 13 araçlı function calling (sipariş, stok, kargo, analitik, müşteri, RAG)
- Konuşma bağlamını koruma (per-phone geçmiş)
- Ürün kataloğu üzerinde anlamsal arama (RAG + fallback keyword)

### Sipariş Yönetimi
- Manuel ve marketplace (Trendyol, Hepsiburada, n11) sipariş takibi
- Platform badge görünümü (renk kodlu)
- Durum geçişleri: beklemede → işlemde → kargoda → teslim edildi
- Ödeme durumu takibi (ödendi / ödenmedi / kısmi)
- Kargoya verilince otomatik stok düşürme

### Stok Yönetimi
- Multi-depo desteği (Ana Depo, Kasa, Vitrin)
- Kritik stok eşiği uyarısı (WhatsApp + otomatik e-posta)
- Satış hızına göre akıllı sipariş miktarı önerisi
- Tedarikçiye entegre yeniden sipariş e-postası

### Kargo Takip
- Kargo firması simülasyonu (tek tıkla toplu güncelleme)
- Durum değişikliğinde otomatik müşteri WhatsApp bildirimi
- Teslim Edildi → bağlı sipariş otomatik kapanır
- Gecikme bildirimi (admin + müşteri)

### Analitik ve Tahmin
- Gerçek zamanlı satış özeti (günlük/haftalık/aylık)
- Top 5 ürün sıralaması (adet + ciro)
- 90 günlük veri ile haftalık satış tahmini
- Stok yeterliliği uyarısı (tahmin × 2 < stok)
- Platform dağılımı (marketplace vs manuel)
- Kâr marjı hesabı (satış - alış)

### Müşteri & Tedarikçi CRM
- Arama, oluşturma, güncelleme, silme
- Sipariş geçmişi ve toplam harcama takibi
- Top müşteri ve tedarikçi sıralaması

### Bildirimler
- WhatsApp: Twilio (üretim) → Meta Business → CallMeBot (demo) öncelik sırası
- E-posta: Resend API → Gmail SMTP fallback
- Demo modunda tüm e-postalar `DEMO_EMAIL` adresine yönlendirilir

---

## Teknoloji Yığını

| Katman | Teknoloji | Versiyon |
|--------|-----------|----------|
| **Backend API** | FastAPI | 0.115+ |
| **LLM & Function Calling** | Google Gemini 2.5 Flash | API v1beta |
| **Anlamsal Arama (RAG)** | Gemini text-embedding-004 + Cosine Similarity | — |
| **Veritabanı** | SQLite + SQLAlchemy ORM | 2.0+ |
| **WhatsApp** | Twilio / Meta Business API / CallMeBot | — |
| **E-posta** | Resend API / Gmail SMTP | — |
| **Auth** | JWT (python-jose) + PBKDF2-SHA256 | HS256 |
| **Kargo API** | Yurtiçi / MNG / PTT / Aras (mock + gerçek) | — |
| **Frontend** | Vanilla JS + HTML/CSS (tek dosya) | — |

---

## Kurulum

### 1. Bağımlılıklar

```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenleri

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

`.env` dosyasında zorunlu alanlar:

```env
GEMINI_API_KEY=buraya_gemini_api_anahtarinizi_yazin
JWT_SECRET=en_az_32_karakter_rastgele_bir_string

ADMIN_PHONE=+905XXXXXXXXX        # Proaktif WhatsApp bildirimleri için
PROACTIVE_CHECK_INTERVAL=60      # Demo için 60s, üretimde 3600
DEMO_EMAIL=sizin@email.com        # Demo e-postalar bu adrese gider
```

WhatsApp için (ücretsiz demo — yalnızca kendi telefonunuza):

```env
CALLMEBOT_APIKEY=123456
CALLMEBOT_PHONE=905XXXXXXXXX
```

### 3. Çalıştırma

```bash
uvicorn app.main:app --reload
```

> Eğer `aura.db` mevcutsa ve eski veri varsa silin — uygulama başlarken takı mağazası demo verisi otomatik yüklenir.

Sunucu ayağa kalktıktan sonra erişim linkleri:

| Sayfa | URL |
|-------|-----|
| **Admin Paneli** | `http://localhost:8000` |
| **WhatsApp Demo** | `http://localhost:8000/demo` |
| **API Dokümantasyonu** | `http://localhost:8000/docs` |

```bash
del aura.db   # Windows
rm aura.db    # Linux/Mac
```

### 4. Giriş

```
URL:    http://localhost:8000
E-posta: admin@aura.ai
Şifre:   aura2026
```

### 5. API Dokümantasyonu (Swagger)

```
http://localhost:8000/docs
```

---

## Demo Senaryoları

### Senaryo 1 — WhatsApp Kargo Sorgulama
> Müşteri: *"128 numaralı siparişim ne zaman gelir?"*

```
KOBIAgent:
  1. get_order_status("ORD-128")           → kargo takip kodu alır
  2. get_cargo_status("TRK-XYZ789")        → gerçek zamanlı konum
  Yanıt: "Güneş Kolyeniz İstanbul Anadolu Dağıtım Merkezi'nde,
           yarın teslim edilmesi bekleniyor."
```

### Senaryo 2 — Stok Sorgulama (RAG)
> Müşteri: *"Güneş kolyenin gümüş rengi var mı?"*

```
KOBIAgent:
  1. search_knowledge_base("güneş kolyesi gümüş")  → ürün detayı (RAG)
  2. get_inventory_status("Güneş Kolyesi - Gümüş") → stok adedi
  Yanıt: "Gümüş versiyonu 3 adet kaldı, 320 TL."
```

### Senaryo 3 — Proaktif Admin Bildirimi
> Arka plan görevi otomatik çalışır

```
Kargo gecikmesi →  "🚨 TRK-GHI999 — Yoğunluk nedeniyle aktarma gecikmesi"
Kritik stok    →  "📉 Güneş Kolyesi - Gümüş: 3 adet kaldı"
               +  Tedarikçiye: "Son 30 günde 8 adet satıldı. Öneri: 24 adet sipariş"
```

### Senaryo 4 — Kargo Firması Senkronizasyonu
> Panel'den "Kargo Firmasından Sorgula" butonuna basılır

```
carrier-sync endpoint:
  - Tüm aktif kargolar rastgele güncellenir (Yolda/Dağıtımda/Teslim Edildi)
  - Her güncellenen kargo için müşteriye WhatsApp bildirimi gönderilir
  - Teslim Edildi olan kargolar bağlı siparişleri otomatik kapatır
```

---

## API Endpoint Referansı

### Sohbet
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/api/chat/` | Gemini sohbet (geçmiş destekli) |
| `GET`  | `/api/chat/daily-briefing` | Günlük operasyon özeti |

### Siparişler
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET`  | `/api/orders/` | Tüm siparişler |
| `GET`  | `/api/orders/pending` | Beklemede/işlemde |
| `GET`  | `/api/orders/{id}` | Sipariş detayı |
| `POST` | `/api/orders/` | Yeni sipariş |
| `PATCH`| `/api/orders/{id}/status` | Durum güncelle (WhatsApp bildirim) |
| `PATCH`| `/api/orders/{id}/payment` | Ödeme durumu güncelle |

### Stok
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET`  | `/api/inventory/` | Tüm stok |
| `GET`  | `/api/inventory/low-stock` | Kritik ürünler |
| `GET`  | `/api/inventory/warehouses` | Depo özeti |
| `GET`  | `/api/inventory/{name}` | Ürün detayı |
| `POST` | `/api/inventory/` | Yeni ürün ekle |
| `PATCH`| `/api/inventory/{name}/stock` | Stok miktarını set et |
| `PATCH`| `/api/inventory/{name}/decrease` | Stoktan belirli miktar düş |

### Kargo
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET`  | `/api/cargo/` | Tüm kargo kayıtları |
| `GET`  | `/api/cargo/delayed` | Geciken kargolar |
| `GET`  | `/api/cargo/track/{code}` | Kargo sorgula (DB → API) |
| `POST` | `/api/cargo/` | Yeni kargo ekle |
| `POST` | `/api/cargo/carrier-sync` | Kargo firması senkronizasyonu |
| `PATCH`| `/api/cargo/{code}/status` | Kargo durumu güncelle |
| `POST` | `/api/cargo/notify-customer` | Müşteriye WhatsApp bildirimi |

### Analitik
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET`  | `/api/analytics/summary` | Kapsamlı iş özeti |
| `GET`  | `/api/analytics/forecast` | Top 5 haftalık satış tahmini |

### Kimlik Doğrulama
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/api/auth/register` | Yeni kullanıcı kaydı |
| `POST` | `/api/auth/login` | JWT token al |
| `GET`  | `/api/auth/me` | Token doğrulama |

### WhatsApp
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/api/whatsapp/webhook` | Twilio webhook |
| `POST` | `/api/whatsapp/webhook/meta` | Meta Business webhook |
| `GET`  | `/api/whatsapp/webhook/meta` | Meta token doğrulama |
| `GET`  | `/api/whatsapp/conversations` | Aktif konuşmalar |

### Diğer
| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| `GET`  | `/api/customers/` | Müşteri listesi (arama destekli) |
| `GET`  | `/api/suppliers/` | Tedarikçi listesi |
| `GET`  | `/api/invoices/{id}` | HTML fatura |
| `POST` | `/api/marketplace/sync` | Platform sipariş senkronizasyonu |
| `GET`  | `/health` | Sistem sağlık kontrolü |

---

## Proje Yapısı

```
modus.ai/
├── app/
│   ├── main.py                      # FastAPI app, lifespan, proaktif monitor, seed data
│   ├── agents/
│   │   └── kobi_agent.py            # Gemini 2.5 Flash + 13 araçlı function calling
│   ├── api/
│   │   └── routes/
│   │       ├── auth.py              # JWT kayıt/giriş
│   │       ├── cargo.py             # Kargo takip + carrier-sync + bildirim
│   │       ├── chat.py              # Web chat + günlük özet
│   │       ├── customers.py         # Müşteri CRUD
│   │       ├── demo.py              # Hackathon demo endpoint'leri
│   │       ├── inventory.py         # Stok CRUD + decrease endpoint
│   │       ├── invoices.py          # HTML fatura oluşturma
│   │       ├── marketplace.py       # Trendyol/Hepsiburada/n11 simülasyonu
│   │       ├── orders.py            # Sipariş CRUD + durum/ödeme güncelleme
│   │       ├── suppliers.py         # Tedarikçi CRUD
│   │       └── whatsapp.py          # Twilio + Meta webhook'ları
│   ├── core/
│   │   └── config.py                # Tüm ortam değişkenleri (Pydantic Settings)
│   ├── db/
│   │   ├── database.py              # SQLAlchemy motor ve session factory
│   │   └── models.py                # 6 ORM tablosu (Order, Inventory, Cargo, User, Customer, Supplier)
│   ├── models/
│   │   └── schemas.py               # Pydantic request/response şemaları
│   ├── services/
│   │   ├── analytics_service.py     # Satış özeti, velocity, 90 günlük forecast
│   │   ├── auth_service.py          # PBKDF2 hash + JWT token yönetimi
│   │   ├── cargo_api_service.py     # Kargo firması API entegrasyonları
│   │   ├── cargo_service.py         # Kargo DB işlemleri + carrier-sync
│   │   ├── customer_service.py      # Müşteri yönetimi + sipariş geçmişi
│   │   ├── inventory_service.py     # Stok CRUD + depo yönetimi
│   │   ├── invoice_service.py       # HTML fatura şablonu
│   │   ├── marketplace_service.py   # Platform senkronizasyon simülasyonu
│   │   ├── notification_service.py  # WhatsApp + E-posta + cargo/order bildirimleri
│   │   ├── order_service.py         # Sipariş CRUD + ödeme yönetimi
│   │   ├── rag_service.py           # Gemini embeddings + keyword fallback arama
│   │   └── supplier_service.py      # Tedarikçi yönetimi
│   └── static/
│       ├── index.html               # Tek dosya web uygulaması (Vanilla JS)
│       └── manifest.json            # PWA manifest
├── data/
│   └── product_catalog.json         # RAG ürün katalogu + SSS (18 ürün)
├── .env.example                     # Örnek ortam değişkenleri
├── requirements.txt
└── README.md
```

---

## WhatsApp Entegrasyon Seçenekleri

### Twilio (Üretim)
1. [Twilio Console](https://console.twilio.com) → Messaging → WhatsApp Sandbox
2. Webhook URL: `https://<alan-adiniz>/api/whatsapp/webhook`
3. `.env`:
   ```env
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```

### Meta Business API (Üretim)
1. [Meta for Developers](https://developers.facebook.com) → WhatsApp Business
2. Webhook: `https://<alan-adiniz>/api/whatsapp/webhook/meta`
3. `.env`:
   ```env
   WHATSAPP_TOKEN=xxxx
   WHATSAPP_PHONE_ID=xxxx
   WHATSAPP_VERIFY_TOKEN=aura_verify_2026
   ```

### CallMeBot (Ücretsiz Demo)
1. WhatsApp'tan `+34 644 93 01 08` numarasına `I allow callmebot to send me messages` mesajı gönder
2. Gelen API key'i `.env`'e ekle:
   ```env
   CALLMEBOT_APIKEY=123456
   CALLMEBOT_PHONE=905XXXXXXXXX
   ```

### Yerel Geliştirme (ngrok)
```bash
ngrok http 8000
# Çıkan URL'i Twilio/Meta webhook ayarına ekle
```

---

## Geliştirici Notları

**Konuşma geçmişi:** WhatsApp konuşmaları telefon numarasına göre sunucu belleğinde tutulur. Üretimde Redis veya veritabanı kullanılması önerilir.

**RAG güvenilirliği:** Gemini embedding API erişilemezse otomatik olarak token tabanlı anahtar kelime aramasına geçilir.

**Kargo API'leri:** `.env`'de API anahtarı tanımlı değilse simüle edilmiş veri döner; demo güvenli çalışır.

**Proaktif görev:** `PROACTIVE_CHECK_INTERVAL=60` ile demo'da her dakika kontrol eder. Çok-worker deploy'larda her worker kendi monitor'ını çalıştırır; üretimde Celery/RQ gibi task queue kullanılması önerilir.

**E-posta demo modu:** `DEMO_EMAIL` tanımlıysa, Resend ücretsiz planının kısıtlamasını aşmak için tüm e-postalar bu adrese yönlendirilir; orjinal alıcı mesaj gövdesine eklenir.

**Veritabanı:** Geliştirme için SQLite idealdir. Üretimde PostgreSQL kullanılması önerilir.

---

*Aura.AI — YZTA 5.0 Hackathon*
