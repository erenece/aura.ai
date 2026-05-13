"""
RAG (Retrieval-Augmented Generation) Servisi.

Ürün katalogu ve SSS veritabanı üzerinde anlamsal arama yapar.
Gemini text-embedding-004 modeli ile vektör gömüleri oluşturur.
API erişimi yoksa otomatik olarak anahtar kelime aramasına geçer.

Kullanım:
    rag = RAGService()
    results = rag.search("güneş kolyesi gümüş fiyat")
"""
import json
import logging
import math
import os

logger = logging.getLogger(__name__)

_CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "product_catalog.json"
)


# ── Vektör yardımcıları ────────────────────────────────────────────────────────

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine(a: list[float], b: list[float]) -> float:
    n = _norm(a) * _norm(b)
    return _dot(a, b) / n if n > 0 else 0.0


# ── Servis ─────────────────────────────────────────────────────────────────────

class RAGService:
    """
    Ürün katalogu + SSS üzerinde anlamsal (veya anahtar kelime tabanlı) arama.

    İlk `search()` çağrısında katalog yüklenir ve tüm öğeler için Gemini
    gömüleri hesaplanır (lazy initialization).
    """

    def __init__(self) -> None:
        self._catalog: list[dict] = []
        self._embeddings: list[list[float]] = []
        self._semantic_enabled = False
        self._ready = False

    # ── İç yükleme ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._ready:
            return

        catalog_path = os.path.abspath(_CATALOG_PATH)
        try:
            with open(catalog_path, encoding="utf-8") as f:
                self._catalog = json.load(f)
            logger.info("RAG: %d katalog öğesi yüklendi", len(self._catalog))
        except FileNotFoundError:
            logger.warning("RAG katalog dosyası bulunamadı: %s", catalog_path)
            self._ready = True
            return
        except json.JSONDecodeError as exc:
            logger.error("RAG katalog JSON hatası: %s", exc)
            self._ready = True
            return

        # Gemini gömüleri — başarısız olursa keyword moduna geç
        try:
            from google import genai
            from app.core.config import settings

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            for item in self._catalog:
                text = self._item_to_text(item)
                result = client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                self._embeddings.append(result.embeddings[0].values)

            self._semantic_enabled = True
            logger.info("RAG: %d öğe için Gemini gömüleri hazırlandı", len(self._catalog))

        except Exception as exc:
            logger.warning(
                "RAG Gemini embedding başarısız (%s) — anahtar kelime moduna geçildi", exc
            )
            self._embeddings = []
            self._semantic_enabled = False

        self._ready = True

    @staticmethod
    def _item_to_text(item: dict) -> str:
        """Katalog öğesini aranabilir tek bir metin dizisine dönüştürür."""
        parts = [
            item.get("name", ""),
            item.get("description", ""),
            item.get("material", ""),
            " ".join(item.get("colors", [])),
            " ".join(item.get("tags", [])),
        ]
        return " ".join(p for p in parts if p).strip()

    # ── Genel arama API'si ─────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Sorguya en uygun katalog öğelerini döndürür.

        Args:
            query: Doğal dil arama sorgusu.
            top_k: Döndürülecek maksimum sonuç sayısı.

        Returns:
            Her biri `score` alanı eklenmiş katalog öğesi listesi.
        """
        self._load()
        if not self._catalog:
            return []

        if self._semantic_enabled:
            return self._semantic_search(query, top_k)
        return self._keyword_search(query, top_k)

    # ── Anlamsal arama (Gemini embeddings) ────────────────────────────────────

    def _semantic_search(self, query: str, top_k: int) -> list[dict]:
        try:
            from google import genai
            from app.core.config import settings

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=query,
            )
            q_emb = result.embeddings[0].values

        except Exception as exc:
            logger.warning("Sorgu gömüsü alınamadı (%s) — keyword aramasına geçildi", exc)
            return self._keyword_search(query, top_k)

        scored = sorted(
            ((i, _cosine(q_emb, emb)) for i, emb in enumerate(self._embeddings)),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            {**self._catalog[i], "score": round(s, 3)}
            for i, s in scored[:top_k]
            if s > 0.25  # Alaka eşiği — düşük benzerlik sonuçları atlanır
        ]

    # ── Anahtar kelime araması (yedek mod) ────────────────────────────────────

    def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        q_lower = query.lower()
        tokens = [t for t in q_lower.split() if len(t) > 1]

        scored: list[tuple[dict, int]] = []
        for item in self._catalog:
            text = self._item_to_text(item).lower()
            hits = sum(1 for t in tokens if t in text)
            if hits > 0:
                scored.append((item, hits))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {**item, "score": float(hits)}
            for item, hits in scored[:top_k]
        ]
