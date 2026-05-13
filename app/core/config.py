from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    APP_NAME: str = "KOBİ Otonom Operasyon Asistanı"
    DEBUG: bool = False
    LOW_STOCK_THRESHOLD: int = 10

    # JWT Auth
    JWT_SECRET: str = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # ── Email (öncelik sırası: Resend → SMTP) ────────────────────────────────
    RESEND_API_KEY: str = ""       # resend.com'dan al — en kolay yöntem
    RESEND_FROM: str = "Aura.AI <onboarding@resend.dev>"  # kendi domain yoksa bu çalışır
    DEMO_EMAIL: str = ""           # Demo: tüm e-postalar bu adrese yönlendirilir (Resend free tier)

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""        # Gmail: Uygulama Şifresi
    SMTP_FROM_NAME: str = "Aura.AI"

    # ── WhatsApp (öncelik sırası: CallMeBot → Meta API) ───────────────────
    CALLMEBOT_APIKEY: str = ""     # Tamamen bedava — callmebot.com
    CALLMEBOT_PHONE: str = ""      # Kendi numaran: 905XXXXXXXXX formatında

    WHATSAPP_TOKEN: str = ""       # Meta Business API (isteğe bağlı)
    WHATSAPP_PHONE_ID: str = ""

    # ── WhatsApp — Twilio (gerçek müşteri telefonlarına gönderim) ─────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""  # sandbox: +14155238886

    # Kargo API anahtarları
    YURTICI_API_KEY: str = ""
    MNG_API_KEY: str = ""
    PTT_API_KEY: str = ""

    # ── Proaktif İzleme ───────────────────────────────────────────────────
    # Yöneticinin WhatsApp numarası — kargo gecikmesi/kritik stok uyarıları
    ADMIN_PHONE: str = ""
    # Gecikme ve stok kontrolü aralığı (saniye). Demo için 60, üretim için 3600.
    PROACTIVE_CHECK_INTERVAL: int = 3600

    # ── Meta WhatsApp API ─────────────────────────────────────────────────
    # Meta webhook doğrulama token'ı (istediğiniz bir değer seçin)
    WHATSAPP_VERIFY_TOKEN: str = "aura_verify_2026"

    class Config:
        env_file = ".env"


settings = Settings()
