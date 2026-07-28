"""
Webhooks for affiliate network conversion notifications.
Networks ping this URL when a sale happens.
"""
from fastapi import APIRouter, Request, Header
from agents.analytics_agent import AnalyticsAgent
from database.database import get_db
from database.models import Product

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/conversion/clickbank")
async def clickbank_conversion(request: Request):
    """ClickBank IPN (Instant Payment Notification) handler."""
    data = await request.form()
    product_name = str(data.get("prod", ""))
    amount = float(data.get("amount", 0))
    commission = float(data.get("commission", 0))
    txn_id = str(data.get("cbreceipt", ""))

    product_id = _find_product_id(product_name)
    if product_id:
        agent = AnalyticsAgent()
        agent.record_conversion(
            product_id=product_id,
            commission=commission,
            sale_amount=amount,
            source="clickbank",
            transaction_id=txn_id,
        )
    return {"status": "received"}


@router.post("/conversion/shareasale")
async def shareasale_conversion(request: Request):
    """ShareASale webhook handler."""
    data = await request.json()
    merchant_id = data.get("merchant_id")
    commission = float(data.get("commission", 0))
    sale_amount = float(data.get("sale_amount", 0))
    txn_id = str(data.get("transaction_id", ""))

    product_id = _find_product_id_by_merchant(str(merchant_id))
    if product_id:
        agent = AnalyticsAgent()
        agent.record_conversion(
            product_id=product_id,
            commission=commission,
            sale_amount=sale_amount,
            source="shareasale",
            transaction_id=txn_id,
        )
    return {"status": "received"}


@router.post("/conversion/manual")
async def manual_conversion(request: Request):
    """Manually record a conversion (for networks without webhooks)."""
    data = await request.json()
    agent = AnalyticsAgent()
    agent.record_conversion(
        product_id=data.get("product_id", 0),
        commission=float(data.get("commission", 0)),
        sale_amount=float(data.get("sale_amount", 0)),
        source=data.get("source", "manual"),
        transaction_id=data.get("transaction_id", ""),
    )
    return {"status": "recorded"}


def _find_product_id(product_name: str) -> int | None:
    with get_db() as db:
        product = db.query(Product).filter(
            Product.name.ilike(f"%{product_name}%")
        ).first()
        return product.id if product else None


def _find_product_id_by_merchant(merchant_id: str) -> int | None:
    with get_db() as db:
        product = db.query(Product).filter(
            Product.affiliate_network == "shareasale"
        ).first()
        return product.id if product else None
