from fastapi import APIRouter, HTTPException
from google.genai.errors import ClientError
from app.models.schemas import ChatRequest, ChatResponse
from app.agents.kobi_agent import KOBIAgent

router = APIRouter()
agent = KOBIAgent()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in request.history]
        reply, tools_used = await agent.chat(request.message, history)
        return ChatResponse(reply=reply, tools_used=tools_used)
    except ClientError as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(
                status_code=429,
                detail="Gemini API kota limiti doldu. Lütfen birkaç dakika bekleyin veya API planınızı kontrol edin.",
            )
        raise HTTPException(status_code=502, detail=f"Gemini API hatası: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-briefing")
async def daily_briefing():
    """Sabah brifingini döner: bekleyen siparişler + kritik stoklar."""
    try:
        reply, _ = await agent.chat(
            "Bugünkü operasyon özetini hazırla: bekleyen siparişler, kritik stoklar ve geciken kargolar."
        )
        return {"briefing": reply}
    except ClientError as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(status_code=429, detail="API kota limiti doldu.")
        raise HTTPException(status_code=502, detail=str(e)[:200])
