import json
import logging
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)
from app.services.inventory_service import InventoryService
from app.services.order_service import OrderService
from app.services.cargo_service import CargoService
from app.services.analytics_service import AnalyticsService
from app.services.customer_service import CustomerService
from app.services.notification_service import NotificationService
from app.services.rag_service import RAGService

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_order_status",
                description="Müşteri sipariş durumunu sorgular",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "order_id": types.Schema(type=types.Type.STRING, description="Sipariş ID'si"),
                    },
                    required=["order_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_inventory_status",
                description="Stok durumunu kontrol eder, kritik seviyeleri bildirir",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "product_name": types.Schema(type=types.Type.STRING, description="Ürün adı (boş bırakılırsa tüm stok)"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="get_cargo_status",
                description="Kargo takip durumunu sorgular",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "tracking_code": types.Schema(type=types.Type.STRING, description="Kargo takip numarası"),
                    },
                    required=["tracking_code"],
                ),
            ),
            types.FunctionDeclaration(
                name="list_pending_orders",
                description="Beklemedeki ve işlemdeki siparişleri listeler",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="prepare_restock_email",
                description="Kritik stoklu ürün için tedarikçiye e-posta taslağı hazırlar",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "product_name": types.Schema(type=types.Type.STRING),
                        "quantity_needed": types.Schema(type=types.Type.INTEGER),
                    },
                    required=["product_name", "quantity_needed"],
                ),
            ),
            types.FunctionDeclaration(
                name="create_order",
                description="Yeni bir müşteri siparişi oluşturur ve sisteme kaydeder",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "customer_name": types.Schema(type=types.Type.STRING, description="Müşteri adı soyadı"),
                        "customer_phone": types.Schema(type=types.Type.STRING, description="Müşteri telefon numarası"),
                        "product": types.Schema(type=types.Type.STRING, description="Sipariş edilen ürün adı"),
                        "quantity": types.Schema(type=types.Type.INTEGER, description="Sipariş miktarı"),
                    },
                    required=["customer_name", "customer_phone", "product", "quantity"],
                ),
            ),
            types.FunctionDeclaration(
                name="update_order_status",
                description="Mevcut bir siparişin durumunu günceller",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "order_id": types.Schema(type=types.Type.STRING, description="Sipariş ID'si"),
                        "status": types.Schema(type=types.Type.STRING, description="Yeni durum: beklemede / işlemde / kargoda / teslim_edildi / iptal"),
                        "tracking_code": types.Schema(type=types.Type.STRING, description="Kargo takip kodu (opsiyonel)"),
                    },
                    required=["order_id", "status"],
                ),
            ),
            types.FunctionDeclaration(
                name="update_inventory_stock",
                description="Bir ürünün stok miktarını günceller",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "product_name": types.Schema(type=types.Type.STRING, description="Ürün adı"),
                        "quantity": types.Schema(type=types.Type.INTEGER, description="Yeni stok miktarı"),
                    },
                    required=["product_name", "quantity"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_analytics_summary",
                description="İş analitiği özeti: toplam ciro, aylık gelir, en çok satan ürünler, sipariş dağılımı",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="list_customers",
                description="Müşteri listesini getirir, isteğe bağlı arama ile filtreleme yapılabilir",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "search": types.Schema(type=types.Type.STRING, description="İsim veya telefon ile arama"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="send_restock_email",
                description="Kritik stoktaki ürün için tedarikçiye gerçek e-posta gönderir",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "product_name": types.Schema(type=types.Type.STRING),
                        "quantity_needed": types.Schema(type=types.Type.INTEGER),
                    },
                    required=["product_name", "quantity_needed"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_knowledge_base",
                description=(
                    "Ürün kataloğu ve SSS veritabanında anlamsal arama yapar (RAG). "
                    "Ürün özellikleri, fiyat, malzeme, renk, kargo süresi, iade politikası, "
                    "yüzük numarası ve garanti gibi konular için kullanın."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="Aranacak ürün adı veya konu (Türkçe doğal dil)",
                        ),
                    },
                    required=["query"],
                ),
            ),
        ]
    )
]

_CONFIG = types.GenerateContentConfig(
    system_instruction=(
        "Sen Aura.AI — butik bir takı mağazasının otonom yapay zeka asistanısın. "
        "Hem müşterilere WhatsApp üzerinden hem de işletme sahibine yardım edersin.\n\n"
        "GÖREVLER:\n"
        "• Müşteri soruları: sipariş takibi, kargo durumu, stok ve ürün bilgisi, iade politikası\n"
        "• İşletme yönetimi: sipariş oluşturma/güncelleme, stok takibi, analitik raporlar\n\n"
        "ARAÇ KULLANIM KURALLARI:\n"
        "• Ürün/SSS soruları → önce search_knowledge_base\n"
        "• Stok sorgusu → get_inventory_status (sonra search_knowledge_base ile zenginleştir)\n"
        "• 'X numaralı sipariş' → get_order_status (ORD-X formatını dene)\n"
        "• Kargo sorgusu → önce get_order_status ile tracking_code bul, sonra get_cargo_status\n"
        "• Ciro/gelir soruları → get_analytics_summary\n\n"
        "YANIT TARZI:\n"
        "Türkçe yaz. Müşteriye samimi ve yardımsever ol. "
        "İşletme sahibine kısa ve aksiyona yönelik ol. "
        "Emoji kullanabilirsin ama aşırıya kaçma."
    ),
    tools=TOOLS,
)


class KOBIAgent:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.order_service = OrderService()
        self.cargo_service = CargoService()
        self.analytics_service = AnalyticsService()
        self.customer_service = CustomerService()
        self.notification_service = NotificationService()
        self.rag_service = RAGService()

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        try:
            return self._run_tool(tool_name, args)
        except Exception as e:
            logger.error("Araç hatası [%s]: %s", tool_name, e, exc_info=True)
            return json.dumps({"error": f"{tool_name} aracı çalışırken hata oluştu: {str(e)}"}, ensure_ascii=False)

    def _run_tool(self, tool_name: str, args: dict) -> str:
        if tool_name == "get_order_status":
            result = self.order_service.get_order(args["order_id"])

        elif tool_name == "get_inventory_status":
            result = self.inventory_service.get_status(args.get("product_name"))

        elif tool_name == "get_cargo_status":
            result = self.cargo_service.track(args["tracking_code"])

        elif tool_name == "list_pending_orders":
            result = self.order_service.list_pending()

        elif tool_name == "prepare_restock_email":
            result = self.cargo_service.draft_restock_email(args["product_name"], args["quantity_needed"])

        elif tool_name == "create_order":
            result = self.order_service.create_order(args)

        elif tool_name == "update_order_status":
            result = self.order_service.update_status(
                args["order_id"], args["status"], args.get("tracking_code")
            )

        elif tool_name == "update_inventory_stock":
            result = self.inventory_service.update_stock(args["product_name"], args["quantity"])

        elif tool_name == "get_analytics_summary":
            result = self.analytics_service.get_summary()

        elif tool_name == "list_customers":
            result = self.customer_service.list_all(search=args.get("search"))

        elif tool_name == "send_restock_email":
            result = self.cargo_service.draft_restock_email(args["product_name"], args["quantity_needed"])

        elif tool_name == "search_knowledge_base":
            results = self.rag_service.search(args["query"])
            result = {"results": results, "count": len(results)}

        else:
            result = {"error": f"Bilinmeyen araç: {tool_name}"}

        return json.dumps(result, ensure_ascii=False, default=str)

    async def chat(self, message: str, history: list = None) -> tuple[str, list[str]]:
        history = history or []
        tools_used: list[str] = []

        gemini_history = [
            types.Content(
                role=h["role"],
                parts=[types.Part.from_text(text=h["content"])],
            )
            for h in history
        ]

        chat_session = _client.chats.create(
            model=settings.GEMINI_MODEL,
            config=_CONFIG,
            history=gemini_history,
        )

        response = chat_session.send_message(message)

        while response.function_calls:
            fc = response.function_calls[0]
            tools_used.append(fc.name)
            tool_result = self._execute_tool(fc.name, dict(fc.args or {}))

            response = chat_session.send_message(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": tool_result},
                )
            )

        try:
            text = response.text or "Yanıt alınamadı, lütfen tekrar deneyin."
        except Exception:
            text = "Yanıt alınamadı, lütfen tekrar deneyin."

        return text, tools_used
