"""
Product Discovery Agent
Finds high-commission affiliate products across networks.
Scores products by EPC (earnings per click) potential.
"""
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import Niche, Product, ProductStatus
from config.settings import (
    AMAZON_ASSOCIATE_TAG, CLICKBANK_API_KEY,
    SHAREASALE_TOKEN, SHAREASALE_SECRET, SHAREASALE_MERCHANT_ID
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert affiliate product researcher.
You evaluate products for affiliate marketing potential based on:
- Commission rate and cookie duration
- Product quality and reviews
- Sales page conversion potential
- Refund rates and merchant reputation
- EPC (earnings per click) potential

Always respond with valid JSON only."""


class ProductDiscoveryAgent(BaseAgent):
    name = "ProductDiscoveryAgent"

    def execute(self, niche_name: str | None = None, **kwargs) -> dict:
        with get_db() as db:
            query = db.query(Niche).filter(Niche.status.in_(["active", "testing"]))
            if niche_name:
                query = query.filter(Niche.name == niche_name)
            niches = query.all()
            niche_data = [{"id": n.id, "name": n.name, "keywords": n.keywords} for n in niches]

        total_found = 0
        for niche in niche_data:
            products = self._discover_products_for_niche(niche["name"])
            for p in products:
                self._save_product(p, niche["id"])
                total_found += 1

        return {"products_discovered": total_found, "niches_processed": len(niche_data)}

    def _discover_products_for_niche(self, niche_name: str) -> list[dict]:
        """Use Claude to generate a list of real affiliate products to research."""
        prompt = f"""For the affiliate marketing niche: "{niche_name}"

Identify 5 specific, real affiliate products I should promote. For each product provide details based on your knowledge of typical commission structures.

Return a JSON array:
[
  {{
    "name": "Product Name",
    "affiliate_network": "amazon|clickbank|shareasale|cj|impact|direct",
    "product_url": "https://example.com/product",
    "commission_rate": 15.0,
    "commission_fixed": 0.0,
    "price": 97.0,
    "cookie_duration": 30,
    "description": "Brief product description",
    "pros": ["pro1", "pro2", "pro3"],
    "cons": ["con1", "con2"],
    "rating": 4.5,
    "gravity": 75.0,
    "why_promote": "Why this is a great affiliate product"
  }}
]

Focus on:
- High commission rates (20%+ for digital, 5%+ for physical)
- Proven converters (high gravity on ClickBank, top sellers on Amazon)
- Long cookie duration (30+ days preferred)
- Products people actually need and buy"""
        try:
            products = self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=3000)
            if isinstance(products, list):
                return products
            return []
        except Exception as e:
            logger.error(f"Product discovery failed for {niche_name}: {e}")
            return []

    def _save_product(self, product_data: dict, niche_id: int):
        with get_db() as db:
            existing = db.query(Product).filter(
                Product.name == product_data.get("name"),
                Product.niche_id == niche_id
            ).first()

            if existing:
                existing.commission_rate = product_data.get("commission_rate")
                existing.price = product_data.get("price")
                existing.updated_at = datetime.utcnow()
                return

            product = Product(
                name=product_data.get("name", "Unknown"),
                niche_id=niche_id,
                affiliate_network=product_data.get("affiliate_network", "unknown"),
                product_url=product_data.get("product_url", ""),
                affiliate_url=product_data.get("product_url", ""),  # Updated when link is generated
                commission_rate=product_data.get("commission_rate", 0),
                commission_fixed=product_data.get("commission_fixed", 0),
                price=product_data.get("price", 0),
                cookie_duration=product_data.get("cookie_duration", 30),
                description=product_data.get("description", ""),
                pros=product_data.get("pros", []),
                cons=product_data.get("cons", []),
                rating=product_data.get("rating", 0),
                gravity=product_data.get("gravity", 0),
                status=ProductStatus.testing,
            )
            db.add(product)

    def score_product(self, product: Product) -> float:
        """Score a product 0-100 for promotion priority."""
        score = 0.0
        # Commission rate weight
        if product.commission_rate:
            score += min(product.commission_rate, 50) * 0.5
        # Cookie duration
        if product.cookie_duration:
            score += min(product.cookie_duration / 90 * 20, 20)
        # Rating
        if product.rating:
            score += product.rating / 5 * 20
        # Gravity (ClickBank) or gravity-equivalent
        if product.gravity:
            score += min(product.gravity / 200 * 10, 10)
        return round(score, 2)

    def evaluate_product_with_ai(self, product_name: str, niche: str) -> dict:
        """Deep AI evaluation of a specific product."""
        prompt = f"""Evaluate this affiliate product for promotion:
Product: {product_name}
Niche: {niche}

Return JSON:
{{
  "overall_score": <0-100>,
  "conversion_potential": <0-100>,
  "content_angles": ["angle1", "angle2", "angle3"],
  "target_audience": "description",
  "best_traffic_sources": ["source1", "source2"],
  "email_subject_ideas": ["subject1", "subject2"],
  "concerns": ["concern1"],
  "recommendation": "promote|skip|test"
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Product evaluation failed: {e}")
            return {}
