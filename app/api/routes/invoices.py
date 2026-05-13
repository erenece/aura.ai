from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from app.services.invoice_service import generate_invoice_html

router = APIRouter()


@router.get("/{order_id}", response_class=HTMLResponse)
def get_invoice(order_id: str):
    html = generate_invoice_html(order_id.upper())
    if html is None:
        raise HTTPException(status_code=404, detail=f"Sipariş bulunamadı: {order_id}")
    return HTMLResponse(content=html)
