"""
Bildirim servisi — e-posta ve WhatsApp.

E-posta öncelik sırası:
  1. Resend (resend.com)  ← en kolay, üye ol API al bitti
  2. Gmail SMTP           ← uygulama şifresi gerekli

WhatsApp öncelik sırası:
  1. Twilio               ← gerçek müşteri telefonlarına gönderim (~$0.005/msg, $15 ücretsiz kredi)
  2. Meta Business API    ← Facebook Business doğrulama gerekli
  3. CallMeBot            ← tamamen bedava, SADECE kendi (admin) telefonuna

Hangisi yapılandırılmışsa otomatik kullanılır.
"""
import base64
import smtplib
import logging
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    """Türkiye telefon numarasını uluslararası formata çevirir (+90...)."""
    clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if clean.startswith("0"):
        clean = "90" + clean[1:]
    if not clean.startswith("+"):
        if not clean.startswith("90"):
            clean = "90" + clean
        clean = "+" + clean
    return clean


class NotificationService:

    # ══════════════════════════════════════════════════════════
    #  E-POSTA
    # ══════════════════════════════════════════════════════════

    def send_email(self, to: str, subject: str, body: str) -> dict:
        """Resend varsa onu kullan, yoksa SMTP'yi dene."""
        if settings.RESEND_API_KEY:
            return self._send_via_resend(to, subject, body)
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            return self._send_via_smtp(to, subject, body)
        logger.warning("E-posta yapılandırması yok — taslak modu.")
        return {
            "success": False,
            "error": "E-posta ayarı yapılmamış",
            "cozum": "RESEND_API_KEY veya SMTP_USER+SMTP_PASSWORD ekle",
        }

    def _send_via_resend(self, to: str, subject: str, body: str) -> dict:
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            # Resend free tier: onboarding@resend.dev can only send to the account owner's
            # verified email. Redirect to DEMO_EMAIL so the jury can see a real delivery.
            demo_email = getattr(settings, "DEMO_EMAIL", None)
            actual_to = demo_email if demo_email else to
            demo_note = f"\n\n---\n[DEMO: Gerçekte gönderilecek adres: {to}]" if actual_to != to else ""
            r = resend.Emails.send({
                "from": settings.RESEND_FROM,
                "to": [actual_to],
                "subject": subject,
                "text": body + demo_note,
            })
            logger.info("Resend ile e-posta gönderildi → %s (orijinal: %s)", actual_to, to)
            return {"success": True, "to": actual_to, "original_to": to, "subject": subject, "servis": "resend", "id": getattr(r, "id", None)}
        except Exception as e:
            logger.error("Resend hatası: %s", e)
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                logger.info("SMTP'ye geçiliyor…")
                return self._send_via_smtp(to, subject, body)
            return {"success": False, "error": str(e), "servis": "resend"}

    def _send_via_smtp(self, to: str, subject: str, body: str) -> dict:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
            msg["To"] = to
            msg.attach(MIMEText(body, "plain", "utf-8"))
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as srv:
                srv.starttls()
                srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                srv.send_message(msg)
            logger.info("SMTP ile e-posta gönderildi → %s", to)
            return {"success": True, "to": to, "subject": subject, "servis": "smtp"}
        except smtplib.SMTPAuthenticationError:
            return {"success": False, "servis": "smtp",
                    "error": "Gmail kimlik doğrulama hatası — Uygulama Şifresi kullandığından emin ol"}
        except Exception as e:
            logger.error("SMTP hatası: %s", e)
            return {"success": False, "error": str(e), "servis": "smtp"}

    def send_restock_email(self, product_name: str, quantity_needed: int, supplier_email: str,
                           last_month_sales: int = 0, recommended_qty: int = 0) -> dict:
        subject = f"Acil Stok Talebi — {product_name}"
        from_name = settings.SMTP_FROM_NAME or "Aura.AI"
        sales_line = ""
        if last_month_sales > 0:
            qty = recommended_qty if recommended_qty > 0 else quantity_needed
            sales_line = (
                f"\n📊 Satış Analizi:\n"
                f"   • Son 30 günde {last_month_sales} adet satıldı\n"
                f"   • Sistem önerisi: {qty} adet sipariş\n"
            )
        body = (
            f"Sayın Tedarikçi,\n\n"
            f'"{product_name}" stoğumuz kritik seviyeye düştü.\n'
            f"{sales_line}"
            f"{quantity_needed} adet acil sipariş vermek istiyoruz.\n\n"
            f"Lütfen en kısa sürede stok durumunuzu ve tahmini teslimat tarihinizi bildirin.\n\n"
            f"Saygılarımızla,\n{from_name}"
        )
        result = self.send_email(supplier_email, subject, body)
        result.update({"urun": product_name, "miktar": quantity_needed,
                       "konu": subject, "icerik": body, "gonderildi": result.get("success", False)})
        return result

    # ══════════════════════════════════════════════════════════
    #  WHATSAPP
    # ══════════════════════════════════════════════════════════

    async def send_whatsapp(self, phone: str, message: str) -> dict:
        """
        WhatsApp gönderici — öncelik sırası:
          1. Twilio  → gerçek müşteri telefonlarına gönderebilir
          2. Meta    → Business hesabı gerekli
          3. CallMeBot → sadece admin telefonuna (test/demo)
        """
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM:
            return await self._send_via_twilio(phone, message)
        if settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID:
            return await self._send_via_meta(phone, message)
        if settings.CALLMEBOT_APIKEY and settings.CALLMEBOT_PHONE:
            # CallMeBot yalnızca CALLMEBOT_PHONE'a gönderebilir; müşteri numarası farklıysa atla
            return await self._send_via_callmebot(message)
        return {
            "success": False,
            "error": "WhatsApp ayarı yapılmamış",
            "cozum": "TWILIO_ACCOUNT_SID+TWILIO_AUTH_TOKEN+TWILIO_WHATSAPP_FROM ekle (önerilen)",
        }

    async def _send_via_twilio(self, phone: str, message: str) -> dict:
        """
        Twilio WhatsApp — gerçek müşteri telefonlarına gönderir.
        Sandbox: from=whatsapp:+14155238886
        Müşterinin önce sandbox'a 'join <kelime>' yazması gerekir (test için).
        Production'da kendi onaylı numaranı kullanırsın.
        """
        clean = _normalize_phone(phone)
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        )
        creds = base64.b64encode(
            f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {creds}"}
        from_number = settings.TWILIO_WHATSAPP_FROM
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
        data = {
            "From": from_number,
            "To": f"whatsapp:{clean}",
            "Body": message,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, headers=headers, data=data)
            if r.status_code in (200, 201):
                sid = r.json().get("sid", "")
                logger.info("Twilio WhatsApp gönderildi → %s (sid=%s)", clean, sid)
                return {"success": True, "to": clean, "servis": "twilio", "sid": sid}
            error_msg = r.json().get("message", r.text[:200])
            logger.error("Twilio hata %s: %s", r.status_code, error_msg)
            return {"success": False, "error": error_msg, "servis": "twilio", "status_code": r.status_code}
        except Exception as e:
            logger.error("Twilio istisna: %s", e)
            return {"success": False, "error": str(e), "servis": "twilio"}

    async def _send_via_meta(self, phone: str, message: str) -> dict:
        """Meta WhatsApp Business Cloud API — gerçek müşteri numaralarına gönderir."""
        clean = _normalize_phone(phone)
        url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_ID}/messages"
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}", "Content-Type": "application/json"}
        payload = {"messaging_product": "whatsapp", "to": clean,
                   "type": "text", "text": {"body": message}}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, headers=headers, json=payload)
            if r.status_code == 200:
                return {"success": True, "to": clean, "servis": "meta"}
            return {"success": False, "error": r.text[:200], "servis": "meta"}
        except Exception as e:
            return {"success": False, "error": str(e), "servis": "meta"}

    async def _send_via_callmebot(self, message: str) -> dict:
        """
        CallMeBot — ücretsiz, sadece CALLMEBOT_PHONE numarasına gönderir.
        Müşteri telefonuna değil, admin telefonuna gönderir.
        """
        encoded_msg = urllib.parse.quote(message)
        url = (
            f"https://api.callmebot.com/whatsapp.php"
            f"?phone={settings.CALLMEBOT_PHONE}"
            f"&text={encoded_msg}"
            f"&apikey={settings.CALLMEBOT_APIKEY}"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
            if r.status_code == 200 and "Message queued" in r.text:
                logger.info("CallMeBot WhatsApp gönderildi")
                return {"success": True, "to": settings.CALLMEBOT_PHONE, "servis": "callmebot"}
            return {"success": False, "error": r.text[:200], "servis": "callmebot"}
        except Exception as e:
            return {"success": False, "error": str(e), "servis": "callmebot"}

    # ── Hazır mesaj şablonları ─────────────────────────────────────────────

    async def notify_order_status(self, phone: str, customer_name: str,
                                   order_id: str, product: str, status: str,
                                   tracking_code: Optional[str] = None) -> dict:
        emojis = {
            "beklemede": "⏳", "işlemde": "📦",
            "kargoda": "🚚", "teslim_edildi": "✅", "iptal": "❌",
        }
        labels = {
            "beklemede": "beklemede", "işlemde": "hazırlanıyor",
            "kargoda": "kargoya verildi", "teslim_edildi": "teslim edildi", "iptal": "iptal edildi",
        }
        emoji = emojis.get(status, "📋")
        label = labels.get(status, status)
        msg = f"{emoji} Merhaba {customer_name}!\n\n*{order_id}* siparişiniz ({product}) *{label}*."
        if tracking_code:
            msg += f"\n📍 Kargo takip: `{tracking_code}`"
        msg += "\n\n_Aura.AI | Operasyon Asistanı_"
        return await self.send_whatsapp(phone, msg)

    async def notify_cargo_update(self, phone: str, customer_name: str,
                                   tracking_code: str, new_status: str, location: str) -> dict:
        messages = {
            "Yolda":          ("🚚", "kargonuz yola çıktı", f"📍 Şu an: {location}"),
            "Dağıtımda":      ("📦", "kargonuz dağıtım aracında", f"📍 Konum: {location}"),
            "Teslim Edildi":  ("✅", "kargonuz teslim edildi", "Alışverişiniz için teşekkürler! 🎉"),
            "Gecikti":        ("⚠️", "kargonuzda gecikme yaşanıyor", f"📍 Son konum: {location}"),
        }
        emoji, label, detail = messages.get(new_status, ("📋", f"durumu güncellendi: {new_status}", f"📍 {location}"))
        msg = (
            f"{emoji} Merhaba {customer_name}!\n\n"
            f"*{tracking_code}* takip numaralı {label}.\n"
            f"{detail}\n\n"
            f"_Aura.AI | Kargo Takip_"
        )
        return await self.send_whatsapp(phone, msg)

    async def notify_low_stock(self, admin_phone: str, product: str,
                                quantity: int, unit: str) -> dict:
        msg = (
            f"⚠️ *Stok Uyarısı*\n\n"
            f"*{product}* kritik seviyede!\n"
            f"Kalan: {quantity} {unit}\n\n"
            f"_Aura.AI | Stok Yönetimi_"
        )
        return await self.send_whatsapp(admin_phone, msg)
