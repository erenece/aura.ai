from fastapi import APIRouter
from app.services.analytics_service import AnalyticsService

router = APIRouter()
service = AnalyticsService()


@router.get("/summary")
def analytics_summary():
    return service.get_summary()


@router.get("/forecast", summary="Önümüzdeki hafta satış tahmini — top 5 ürün")
def analytics_forecast():
    return service.get_forecast()
