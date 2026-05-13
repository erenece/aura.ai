from datetime import datetime
from app.services.order_service import OrderService

_order_svc = OrderService()


def generate_invoice_html(order_id: str) -> str:
    order = _order_svc.get_order(order_id)
    if "error" in order:
        return None

    now = datetime.now()
    invoice_no = f"INV-{order_id}-{now.strftime('%Y%m')}"
    total = order.get("total_amount", 0.0)
    kdv = round(total * 0.20, 2)
    genel_toplam = round(total + kdv, 2)
    payment_status = order.get("payment_status", "ödenmedi")
    payment_badge = (
        '<span style="background:#16a34a;color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">ÖDENDİ</span>'
        if payment_status == "ödendi" else
        '<span style="background:#dc2626;color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">ÖDENMEDİ</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Fatura {invoice_no}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 32px; color: #1e293b; background: #f8fafc; }}
  .invoice {{ max-width: 720px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; border-bottom: 2px solid #e2e8f0; padding-bottom: 24px; }}
  .brand {{ font-size: 24px; font-weight: 700; color: #0ea5e9; }}
  .brand span {{ color: #64748b; font-size: 13px; font-weight: 400; display: block; margin-top: 4px; }}
  .invoice-meta {{ text-align: right; }}
  .invoice-meta h2 {{ margin: 0 0 4px; font-size: 22px; color: #334155; }}
  .invoice-meta p {{ margin: 2px 0; color: #64748b; font-size: 13px; }}
  .parties {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
  .party h4 {{ margin: 0 0 8px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; }}
  .party p {{ margin: 2px 0; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
  th {{ background: #f1f5f9; padding: 10px 12px; text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }}
  td {{ padding: 12px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
  .totals {{ display: flex; justify-content: flex-end; }}
  .totals table {{ width: 280px; }}
  .totals td {{ border: none; padding: 6px 12px; }}
  .totals .total-row td {{ font-weight: 700; font-size: 16px; border-top: 2px solid #e2e8f0; padding-top: 12px; color: #0ea5e9; }}
  .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .invoice {{ box-shadow: none; }} }}
</style>
</head>
<body>
<div class="invoice">
  <div class="header">
    <div class="brand">
      Aura.AI
      <span>Otonom Takı Mağazası Asistanı</span>
    </div>
    <div class="invoice-meta">
      <h2>FATURA</h2>
      <p><strong>{invoice_no}</strong></p>
      <p>Tarih: {now.strftime('%d.%m.%Y')}</p>
      <p>Ödeme: {payment_badge}</p>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h4>Satıcı</h4>
      <p><strong>Aura.AI İşletme</strong></p>
      <p>admin@aura.ai</p>
    </div>
    <div class="party">
      <h4>Alıcı</h4>
      <p><strong>{order.get('customer_name', '')}</strong></p>
      <p>{order.get('customer_phone', '')}</p>
      <p>{order.get('customer_address', '') or ''}</p>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Ürün / Hizmet</th>
        <th>Miktar</th>
        <th>Birim Fiyat</th>
        <th>Tutar</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>{order.get('product', '')}</td>
        <td>{order.get('quantity', 0)} adet</td>
        <td>{order.get('unit_price', 0.0):.2f} ₺</td>
        <td>{total:.2f} ₺</td>
      </tr>
    </tbody>
  </table>

  <div class="totals">
    <table>
      <tr><td>Ara Toplam</td><td style="text-align:right">{total:.2f} ₺</td></tr>
      <tr><td>KDV (%20)</td><td style="text-align:right">{kdv:.2f} ₺</td></tr>
      <tr class="total-row"><td>Genel Toplam</td><td style="text-align:right">{genel_toplam:.2f} ₺</td></tr>
    </table>
  </div>

  {"<p style='margin-top:16px;color:#16a34a;font-size:13px;'>Ödeme yöntemi: " + (order.get('payment_method') or '').replace('_', ' ').title() + "</p>" if order.get('payment_method') else ""}

  <div class="footer">
    Bu fatura Aura.AI tarafından otomatik oluşturulmuştur. • {now.strftime('%d.%m.%Y %H:%M')}
    <br><button onclick="window.print()" style="margin-top:12px;padding:8px 20px;background:#0ea5e9;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;">Yazdır / PDF Kaydet</button>
  </div>
</div>
</body>
</html>"""
