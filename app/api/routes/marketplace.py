from fastapi import APIRouter, Query
from typing import Optional
from app.services.marketplace_service import MarketplaceService

router = APIRouter()
service = MarketplaceService()


@router.post("/sync")
def sync_marketplace(
    platform: str = Query(default="trendyol", description="trendyol | hepsiburada | n11"),
    count: int = Query(default=3, ge=1, le=20),
):
    """Marketplace'den yeni siparişleri içe aktar (demo modunda simülasyon çalışır)."""
    return service.sync_orders(platform, count)


@router.get("/stats")
def platform_stats():
    """Her kanaldan gelen sipariş ve ciro dağılımı."""
    return service.get_platform_stats()
