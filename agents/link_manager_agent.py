"""
Link Manager Agent
Creates, cloaks, and tracks affiliate links.
Monitors for dead links and reports performance.
"""
import hashlib
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import AffiliateLink, Product, LinkClick
from config.settings import BASE_URL

logger = logging.getLogger(__name__)


class LinkManagerAgent(BaseAgent):
    name = "LinkManagerAgent"

    def execute(self, **kwargs) -> dict:
        created = self._create_missing_links()
        dead = self._check_dead_links()
        return {"links_created": created, "dead_links_found": dead}

    def create_affiliate_link(self, product_id: int, custom_code: str | None = None) -> AffiliateLink | None:
        with get_db() as db:
            product = db.query(Product).filter(Product.id == product_id).first()
            if not product:
                return None

            # Check if link already exists
            existing = db.query(AffiliateLink).filter(
                AffiliateLink.product_id == product_id
            ).first()
            if existing:
                return existing

            short_code = custom_code or self._generate_short_code(product.name, product_id)
            cloaked_url = f"{BASE_URL}/go/{short_code}"

            link = AffiliateLink(
                product_id=product_id,
                short_code=short_code,
                original_url=product.affiliate_url or product.product_url or "",
                cloaked_url=cloaked_url,
                is_active=True,
            )
            db.add(link)
            db.flush()

            # Update the product's affiliate URL
            product.affiliate_url = cloaked_url

            # Return a copy of the data before session closes
            link_data = {
                "id": link.id,
                "short_code": short_code,
                "cloaked_url": cloaked_url,
            }

        return link_data

    def _generate_short_code(self, name: str, product_id: int) -> str:
        raw = f"{name}{product_id}{datetime.utcnow().timestamp()}"
        return hashlib.md5(raw.encode()).hexdigest()[:8]

    def _create_missing_links(self) -> int:
        with get_db() as db:
            # Find products without affiliate links
            linked_product_ids = [r[0] for r in db.query(AffiliateLink.product_id).all()]
            products_without_links = db.query(Product).filter(
                Product.id.notin_(linked_product_ids),
                Product.status.in_(["active", "testing"])
            ).all()
            product_ids = [p.id for p in products_without_links]

        created = 0
        for product_id in product_ids:
            result = self.create_affiliate_link(product_id)
            if result:
                created += 1
        return created

    def track_click(self, short_code: str, ip: str, user_agent: str,
                    referrer: str, source: str) -> str | None:
        """Record a click and return the destination URL."""
        with get_db() as db:
            link = db.query(AffiliateLink).filter(
                AffiliateLink.short_code == short_code,
                AffiliateLink.is_active == True
            ).first()

            if not link:
                return None

            link.total_clicks = (link.total_clicks or 0) + 1
            destination = link.original_url

            click = LinkClick(
                link_id=link.id,
                product_id=link.product_id,
                ip_address=ip[:45] if ip else None,
                user_agent=user_agent[:499] if user_agent else None,
                referrer=referrer[:499] if referrer else None,
                source=source[:99] if source else "direct",
            )
            db.add(click)

        return destination

    def _check_dead_links(self) -> int:
        with get_db() as db:
            links = db.query(AffiliateLink).filter(AffiliateLink.is_active == True).all()
            links_data = [{"id": l.id, "url": l.original_url} for l in links]

        dead = 0
        for link_data in links_data:
            url = link_data.get("url", "")
            if not url:
                continue
            try:
                response = requests.head(url, timeout=10, allow_redirects=True)
                if response.status_code >= 400:
                    with get_db() as db:
                        link = db.query(AffiliateLink).filter(AffiliateLink.id == link_data["id"]).first()
                        if link:
                            link.is_active = False
                    dead += 1
                    logger.warning(f"Dead link found: {url} (status {response.status_code})")
            except Exception:
                pass  # Network issues are not necessarily dead links

        return dead

    def get_link_stats(self, product_id: int | None = None) -> list[dict]:
        with get_db() as db:
            query = db.query(AffiliateLink)
            if product_id:
                query = query.filter(AffiliateLink.product_id == product_id)
            links = query.all()

            stats = []
            for link in links:
                click_count = db.query(LinkClick).filter(
                    LinkClick.link_id == link.id
                ).count()
                source_breakdown = {}
                clicks = db.query(LinkClick).filter(LinkClick.link_id == link.id).all()
                for click in clicks:
                    src = click.source or "direct"
                    source_breakdown[src] = source_breakdown.get(src, 0) + 1

                stats.append({
                    "link_id": link.id,
                    "short_code": link.short_code,
                    "product_id": link.product_id,
                    "total_clicks": link.total_clicks or 0,
                    "tracked_clicks": click_count,
                    "source_breakdown": source_breakdown,
                    "is_active": link.is_active,
                    "cloaked_url": link.cloaked_url,
                })
        return stats

    def deactivate_link(self, short_code: str) -> bool:
        with get_db() as db:
            link = db.query(AffiliateLink).filter(
                AffiliateLink.short_code == short_code
            ).first()
            if link:
                link.is_active = False
                return True
        return False
