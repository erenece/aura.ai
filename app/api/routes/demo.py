"""
Demo Router — Hackathon jürisi için iki aktörlü mimariyi gösterir.

Aktör 1 (Müşteri): POST /api/demo/message
Aktör 2 (İşletme Sahibi): Admin paneli /
"""
import logging
from fastapi import APIRouter, HTTPException
from google.genai.errors import ClientError
from pydantic import BaseModel
from app.agents.kobi_agent import KOBIAgent

logger = logging.getLogger(__name__)
router = APIRouter()
_agent = KOBIAgent()

_conversations: dict[str, list[dict]] = {}


class CustomerMessage(BaseModel):
    phone: str = "+905321234567"
    message: str


class AgentResponse(BaseModel):
    phone: str
    customer_message: str
    agent_reply: str
    tools_used: list[str]


@router.post(
    "/message",
    response_model=AgentResponse,
    summary="Aktör 1 — Müşteri WhatsApp mesajı gönder",
    description=(
        "**Demo endpoint.** Müşterinin WhatsApp mesajını simüle eder.\n\n"
        "Ajan niyeti anlar, veritabanını sorgular, doğal Türkçe yanıt üretir.\n\n"
        "**Hazır test mesajları:**\n"
        "- `128 numaralı siparişim ne zaman gelir?`\n"
        "- `Güneş kolyenin gümüş rengi stokta var mı?`\n"
        "- `İade politikanız nedir?`\n"
    ),
)
async def customer_message(body: CustomerMessage) -> AgentResponse:
    history = list(_conversations.get(body.phone, []))
    _conversations.setdefault(body.phone, []).append(
        {"role": "user", "content": body.message}
    )
    try:
        reply, tools_used = await _agent.chat(body.message, history)
    except ClientError as e:
        logger.error("Gemini API hatası [demo]: %s", e)
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(
                status_code=429,
                detail="Gemini API kota limiti doldu. Lütfen birkaç dakika bekleyin.",
            )
        raise HTTPException(status_code=502, detail=f"Gemini API hatası: {str(e)[:200]}")
    except Exception as e:
        logger.error("Demo agent hatası: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent hatası: {str(e)[:300]}")
    _conversations[body.phone].append({"role": "model", "content": reply})
    logger.info("Demo [%s] araçlar: %s", body.phone, tools_used)
    return AgentResponse(
        phone=body.phone,
        customer_message=body.message,
        agent_reply=reply,
        tools_used=tools_used,
    )


@router.delete(
    "/conversation/{phone}",
    summary="Konuşma geçmişini sıfırla",
)
async def reset_conversation(phone: str):
    normalized = phone.replace("%2B", "+").strip()
    _conversations.pop(normalized, None)
    return {"status": "cleared", "phone": normalized}


@router.get(
    "/scenarios",
    summary="Hazır demo senaryoları",
)
async def list_scenarios():
    return {
        "scenarios": [
            {
                "id": 1,
                "title": "Kargo Takibi",
                "message": "128 numaralı siparişim ne zaman gelir?",
                "expected_tools": ["get_order_status", "get_cargo_status"],
            },
            {
                "id": 2,
                "title": "Stok Sorgulama",
                "message": "Güneş kolyenin gümüş rengi stokta var mı, fiyatı ne kadar?",
                "expected_tools": ["search_knowledge_base", "get_inventory_status"],
            },
            {
                "id": 3,
                "title": "İade Politikası (RAG)",
                "message": "İade politikanız nedir?",
                "expected_tools": ["search_knowledge_base"],
            },
            {
                "id": 4,
                "title": "Sipariş Oluşturma",
                "message": "Zümrüt taşlı yüzükten bir adet almak istiyorum, adım Ayşe Yılmaz",
                "expected_tools": ["search_knowledge_base", "get_inventory_status", "create_order"],
            },
        ]
    }
