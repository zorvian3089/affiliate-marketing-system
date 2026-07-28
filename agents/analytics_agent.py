"""
Analytics Agent
Tracks revenue, clicks, conversions, and generates actionable reports.
Identifies what's working and what to scale.
"""
import logging
from datetime import datetime, timedelta, date
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import (
    LinkClick, Conversion, ContentPiece, RevenueSnapshot,
    Product, Niche, EmailCampaign, SocialPost
)
from config.settings import CLAUDE_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert affiliate marketing analyst.
You analyze performance data and provide:
- Revenue attribution by channel, product, content
- Actionable recommendations to increase revenue
- Identification of top performers to scale
- Issues and underperformers to fix or cut

Always respond with valid JSON only."""


class AnalyticsAgent(BaseAgent):
    name = "AnalyticsAgent"

    def execute(self, **kwargs) -> dict:
        snapshot = self._take_daily_snapshot()
        report = self._generate_insights(snapshot)
        return {"snapshot": snapshot, "insights": report}

    def _take_daily_snapshot(self) -> dict:
        today = date.today().isoformat()

        with get_db() as db:
            # Check if snapshot already exists
            existing = db.query(RevenueSnapshot).filter(
                RevenueSnapshot.date == today
            ).first()

            today_dt = datetime.combine(date.today(), datetime.min.time())

            # Clicks today
            total_clicks = db.query(LinkClick).filter(
                LinkClick.clicked_at >= today_dt
            ).count()

            # Conversions today
            conversions = db.query(Conversion).filter(
                Conversion.converted_at >= today_dt
            ).all()
            total_conversions = len(conversions)
            total_revenue = sum(c.commission_earned or 0 for c in conversions)

            # Revenue by source
            revenue_by_source: dict[str, float] = {}
            for c in conversions:
                src = c.source or "unknown"
                revenue_by_source[src] = revenue_by_source.get(src, 0) + (c.commission_earned or 0)

            # Revenue by product
            revenue_by_product: dict[str, float] = {}
            for c in conversions:
                product = db.query(Product).filter(Product.id == c.product_id).first()
                name = product.name if product else "unknown"
                revenue_by_product[name] = revenue_by_product.get(name, 0) + (c.commission_earned or 0)

            # Top content by views
            top_content = db.query(ContentPiece).order_by(
                ContentPiece.views.desc()
            ).limit(5).all()
            top_content_data = [{"title": c.title, "views": c.views, "slug": c.slug} for c in top_content]

            snapshot_data = {
                "date": today,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "total_revenue": round(total_revenue, 2),
                "revenue_by_network": revenue_by_source,
                "revenue_by_niche": {},  # Extended in full version
                "revenue_by_product": revenue_by_product,
                "top_content": top_content_data,
            }

            if existing:
                existing.total_clicks = total_clicks
                existing.total_conversions = total_conversions
                existing.total_revenue = total_revenue
                existing.revenue_by_network = revenue_by_source
                existing.revenue_by_product = revenue_by_product
                existing.top_content = top_content_data
            else:
                snap = RevenueSnapshot(**snapshot_data)
                db.add(snap)

        return snapshot_data

    def get_revenue_summary(self, days: int = 30) -> dict:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with get_db() as db:
            snapshots = db.query(RevenueSnapshot).filter(
                RevenueSnapshot.date >= cutoff.date().isoformat()
            ).order_by(RevenueSnapshot.date).all()

            total_revenue = sum(s.total_revenue or 0 for s in snapshots)
            total_clicks = sum(s.total_clicks or 0 for s in snapshots)
            total_conversions = sum(s.total_conversions or 0 for s in snapshots)
            conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0

            daily_data = [
                {
                    "date": s.date,
                    "revenue": s.total_revenue,
                    "clicks": s.total_clicks,
                    "conversions": s.total_conversions,
                }
                for s in snapshots
            ]

        return {
            "period_days": days,
            "total_revenue": round(total_revenue, 2),
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "conversion_rate": round(conversion_rate, 2),
            "avg_daily_revenue": round(total_revenue / max(days, 1), 2),
            "daily_breakdown": daily_data,
        }

    def get_top_performers(self) -> dict:
        with get_db() as db:
            # Top products by conversions
            products = db.query(Product).all()
            product_stats = []
            for p in products:
                conversions = db.query(Conversion).filter(Conversion.product_id == p.id).all()
                revenue = sum(c.commission_earned or 0 for c in conversions)
                clicks = db.query(LinkClick).filter(LinkClick.product_id == p.id).count()
                epc = revenue / clicks if clicks > 0 else 0
                product_stats.append({
                    "id": p.id,
                    "name": p.name,
                    "clicks": clicks,
                    "conversions": len(conversions),
                    "revenue": round(revenue, 2),
                    "epc": round(epc, 4),
                })
            top_products = sorted(product_stats, key=lambda x: x["revenue"], reverse=True)[:5]

            # Top content by views
            top_content = db.query(ContentPiece).order_by(
                ContentPiece.views.desc()
            ).limit(5).all()
            top_content_data = [
                {"title": c.title, "views": c.views, "slug": c.slug,
                 "keyword": c.target_keyword}
                for c in top_content
            ]

        return {
            "top_products": top_products,
            "top_content": top_content_data,
        }

    def _generate_insights(self, snapshot: dict) -> dict:
        if not snapshot or snapshot.get("total_clicks", 0) == 0:
            return {"message": "Not enough data yet — keep the system running for insights"}

        prompt = f"""Analyze this affiliate marketing daily performance data and provide insights:

Date: {snapshot['date']}
Total Clicks: {snapshot['total_clicks']}
Total Conversions: {snapshot['total_conversions']}
Total Revenue: ${snapshot['total_revenue']}
Conversion Rate: {round(snapshot['total_conversions'] / max(snapshot['total_clicks'], 1) * 100, 2)}%
Revenue by Source: {snapshot['revenue_by_network']}
Top Products: {snapshot['revenue_by_product']}

Return JSON:
{{
  "health_status": "good|warning|critical",
  "key_wins": ["win1", "win2"],
  "issues": ["issue1", "issue2"],
  "top_recommendation": "single most impactful thing to do today",
  "scale_opportunity": "what to double down on",
  "projected_monthly_revenue": <extrapolated estimate>,
  "action_items": ["action1", "action2", "action3"]
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Insights generation failed: {e}")
            return {}

    def record_conversion(self, product_id: int, commission: float,
                          sale_amount: float, source: str, transaction_id: str = "") -> bool:
        with get_db() as db:
            conversion = Conversion(
                product_id=product_id,
                commission_earned=commission,
                sale_amount=sale_amount,
                source=source,
                network_transaction_id=transaction_id,
            )
            db.add(conversion)
        return True
