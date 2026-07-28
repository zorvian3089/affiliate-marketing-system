"""
ClickBank Sales Tracker
Uses ClickBank Analytics API to pull real commission data.
Syncs actual sales into the analytics database.
"""
import logging
import requests
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import Conversion, Product
from config.settings import CLICKBANK_API_KEY, CLICKBANK_NICKNAME

logger = logging.getLogger(__name__)

CB_API_BASE = "https://api.clickbank.com/rest/1.3"
CLICKBANK_NICKNAME = "shanmugap"


class ClickBankTracker(BaseAgent):
    name = "ClickBankTracker"

    def __init__(self):
        super().__init__()
        self.headers = {
            "Authorization": CLICKBANK_API_KEY,
            "Accept": "application/json",
        }

    def execute(self, **kwargs) -> dict:
        orders = self.fetch_recent_orders(days=1)
        synced = self._sync_orders(orders)
        return {"orders_fetched": len(orders), "synced_to_db": synced}

    def fetch_recent_orders(self, days: int = 7) -> list[dict]:
        """Pull recent affiliate sales from ClickBank."""
        end = datetime.utcnow()
        start = end - timedelta(days=days)

        url = f"{CB_API_BASE}/orders/list"
        params = {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "role": "AFFILIATE",
            "site": CLICKBANK_NICKNAME,
        }
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                return data.get("orderData", [])
            else:
                logger.warning(f"ClickBank orders API: {r.status_code} — {r.text[:200]}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch ClickBank orders: {e}")
            return []

    def fetch_analytics_summary(self) -> dict:
        """Get account analytics summary."""
        url = f"{CB_API_BASE}/analytics/vendor/summary/account/{CLICKBANK_NICKNAME}"
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"Analytics API: {r.status_code} — {r.text[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Analytics fetch failed: {e}")
            return {}

    def _sync_orders(self, orders: list[dict]) -> int:
        synced = 0
        with get_db() as db:
            for order in orders:
                txn_id = order.get("receipt", "")
                # Check if already recorded
                existing = db.query(Conversion).filter(
                    Conversion.network_transaction_id == txn_id
                ).first()
                if existing:
                    continue

                vendor = order.get("vendor", "")
                amount = float(order.get("amount", 0))
                commission = float(order.get("affiliate", {}).get("commission", 0))

                # Try to match to a product
                product = db.query(Product).filter(
                    Product.affiliate_network == "clickbank"
                ).first()

                conversion = Conversion(
                    product_id=product.id if product else None,
                    commission_earned=commission,
                    sale_amount=amount,
                    source="clickbank",
                    network_transaction_id=txn_id,
                )
                db.add(conversion)
                synced += 1
        return synced

    def get_hoplink(self, vendor_id: str, tracking_id: str = "") -> str:
        """Build a ClickBank hoplink."""
        url = f"https://{CLICKBANK_NICKNAME}.{vendor_id}.hop.clickbank.net"
        if tracking_id:
            url += f"?tid={tracking_id}"
        return url

    def test_connection(self) -> dict:
        """Test if API key works."""
        url = f"{CB_API_BASE}/orders/list"
        params = {"site": CLICKBANK_NICKNAME, "role": "AFFILIATE"}
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=10)
            return {"status": r.status_code, "connected": r.status_code in [200, 400]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
