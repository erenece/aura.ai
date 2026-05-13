"""
WhatsApp Webhook — Twilio/Meta'dan gelen müşteri mesajlarını işler.

Desteklenen entegrasyonlar:
  • Twilio WhatsApp Sandbox/Production
  • Meta WhatsApp Business Cloud API

Akış:
  1. Müşteri WhatsApp mesajı gönderir
  2. Twilio/Meta → POST /api/whatsapp/webhook
  3. Mesaj KOBIAgent'a (Gemini 2.5 Flash + Function Calling + RAG) iletilir
  4. Yanıt arka planda WhatsApp üzerinden gönderilir (Twilio 15sn timeout için)
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Form, Request, Response

from app.agents.kobi_agent import KOBIAgent
from app.core.config import settings
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter()

_agent = KOBIAgent()
_notif = NotificationService()

# Telefon numarasına göre konuşma geçmişi (bellek içi; üretimde Redis/DB kullanın)
_conversations: dict[str, list[dict]] = {}
_MAX_HISTORY = 20  # Konuşma başına max mesaj sayısı


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────────

def _get_history(phone: str) -> list[dict]:
    return list(_conversations.get(phone, []))


def _push_message(phone: str, role: str, content: str) -> None:
    _conversations.setdefault(phone, []).append({"role": role, "content": content})
    if len(_conversations[phone]) > _MAX_HISTORY:
        _conversations[phone] = _conversations[phone][-_MAX_HISTORY:]


async def _handle_message(phone: str, message: str) -> None:
    """Gelen mesajı işle ve WhatsApp'tan müşteriye yanıtla."""
    try:
        history = _get_history(phone)
        _push_message(phone, "user", message)

        reply, tools_used = await _agent.chat(message, history)
        _push_message(phone, "model", reply)

        logger.info("WhatsApp yanıtlandı [%s] — araçlar: %s", phone, tools_used)
        await _notif.send_whatsapp(phone, reply)

    except Exception as exc:
        logger.exception("WhatsApp işleme hatası [%s]: %s", phone, exc)
        await _notif.send_whatsapp(
            phone,
            "Üzgünüm, şu an bir sorun yaşıyorum. Lütfen birkaç dakika sonra tekrar deneyin.",
        )


# ── Endpoint'ler ───────────────────────────────────────────────────────────────

@router.post("/webhook")
async def twilio_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(default=""),
) -> Response:
    """
    Twilio WhatsApp webhook endpoint'i.

    Twilio Konsol Ayarı:
      Messaging → Active Numbers → Webhook URL:
        https://<domain>/api/whatsapp/webhook  (HTTP POST)
    """
    phone = From.replace("whatsapp:", "").strip()
    message = Body.strip()

    logger.info("Twilio mesajı alındı [sid=%s] [%s]: %.120s", MessageSid[:8], phone, message)

    # Mesajı arka planda işle; Twilio'nun 15 saniyelik zaman aşımını aşmamak için
    background_tasks.add_task(_handle_message, phone, message)

    # Twilio'ya boş TwiML yanıtı döndür — asıl yanıt arka planda WhatsApp API ile gönderilir
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="text/xml",
    )


@router.post("/webhook/meta")
async def meta_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Meta WhatsApp Business Cloud API webhook endpoint'i.

    Meta Developer Konsol Ayarı:
      WhatsApp → Configuration → Webhook URL:
        https://<domain>/api/whatsapp/webhook/meta  (HTTP POST)
    """
    try:
        data = await request.json()
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages", [])

        if not messages:
            return {"status": "no_messages"}

        msg = messages[0]
        phone = "+" + msg["from"]
        text = msg.get("text", {}).get("body", "").strip()

        if not text:
            return {"status": "non_text_message"}

        background_tasks.add_task(_handle_message, phone, text)
        return {"status": "ok", "phone": phone}

    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Meta webhook parse hatası: %s", exc)
        return {"status": "parse_error"}


@router.get("/webhook/meta")
async def meta_verify(request: Request) -> Response:
    """
    Meta webhook token doğrulama.
    Meta, webhook URL'si kaydedilirken bu endpoint'i çağırır.
    """
    params = dict(request.query_params)
    if params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(
            content=params.get("hub.challenge", ""),
            media_type="text/plain",
        )
    logger.warning("Meta webhook doğrulama başarısız — token eşleşmedi")
    return Response(status_code=403)


@router.get("/conversations")
async def list_conversations():
    """
    Aktif WhatsApp konuşmalarını listeler.
    Admin/debug amacıyla kullanılır.
    """
    return {
        phone: {
            "message_count": len(msgs),
            "last_message": msgs[-1] if msgs else None,
        }
        for phone, msgs in _conversations.items()
    }


@router.delete("/conversations/{phone}")
async def clear_conversation(phone: str):
    """Belirli bir telefon numarasının konuşma geçmişini temizler."""
    normalized = phone.replace("%2B", "+").strip()
    if normalized in _conversations:
        del _conversations[normalized]
        return {"status": "cleared", "phone": normalized}
    return {"status": "not_found", "phone": normalized}
