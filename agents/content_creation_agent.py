"""
Content Creation Agent
Generates SEO-optimized affiliate content: blog posts, reviews, comparisons, listicles.
Each piece is designed to rank and convert.
"""
import re
import logging
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import Niche, Product, ContentPiece, ContentStatus
from config.settings import MIN_ARTICLE_WORDS, MAX_ARTICLES_PER_DAY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert affiliate content writer.
You write:
- SEO-optimized articles that rank on Google
- Honest, helpful reviews that build trust
- Comparison articles that drive buying decisions
- Listicles that get shared and linked to

Your content:
- Naturally integrates affiliate links without being spammy
- Includes real pros/cons to build reader trust
- Uses proper H2/H3 heading structure
- Has strong calls-to-action
- Is written in markdown format"""


class ContentCreationAgent(BaseAgent):
    name = "ContentCreationAgent"

    CONTENT_TYPES = ["product_review", "comparison", "best_of_list", "how_to_guide", "buyer_guide"]

    def execute(self, niche_id: int | None = None, max_articles: int | None = None, **kwargs) -> dict:
        limit = max_articles or MAX_ARTICLES_PER_DAY

        with get_db() as db:
            niche_query = db.query(Niche).filter(Niche.status.in_(["active", "testing"]))
            if niche_id:
                niche_query = niche_query.filter(Niche.id == niche_id)
            niches = niche_query.all()
            niche_data = [{"id": n.id, "name": n.name, "keywords": n.keywords or []} for n in niches]

            # Get products for content
            products = db.query(Product).filter(Product.status.in_(["active", "testing"])).all()
            product_data = [
                {"id": p.id, "name": p.name, "niche_id": p.niche_id,
                 "commission_rate": p.commission_rate, "price": p.price,
                 "description": p.description, "pros": p.pros, "cons": p.cons}
                for p in products
            ]

        created = 0
        for niche in niche_data:
            if created >= limit:
                break
            niche_products = [p for p in product_data if p["niche_id"] == niche["id"]]
            keywords = niche["keywords"][:10] if niche["keywords"] else []

            for keyword in keywords:
                if created >= limit:
                    break
                content_type = self._choose_content_type(keyword, niche_products)
                piece = self._create_content(niche, keyword, content_type, niche_products)
                if piece:
                    self._save_content(piece, niche["id"])
                    created += 1

        return {"articles_created": created}

    def _choose_content_type(self, keyword: str, products: list) -> str:
        kw = keyword.lower()
        if "best" in kw or "top" in kw:
            return "best_of_list"
        if "vs" in kw or "versus" in kw or "compare" in kw:
            return "comparison"
        if "review" in kw:
            return "product_review"
        if "how to" in kw or "guide" in kw or "ways" in kw:
            return "how_to_guide"
        return "buyer_guide"

    def _create_content(self, niche: dict, keyword: str, content_type: str, products: list) -> dict | None:
        product_info = ""
        if products:
            p = products[0]
            product_info = f"\nFeatured product: {p['name']} (${p['price']}, {p['commission_rate']}% commission)"
            if p.get("pros"):
                product_info += f"\nPros: {', '.join(p['pros'][:3])}"
            if p.get("cons"):
                product_info += f"\nCons: {', '.join(p['cons'][:2])}"

        type_instructions = {
            "product_review": f"Write a comprehensive honest product review for someone searching '{keyword}'. Include pros, cons, who it's for, verdict. At least 1500 words.",
            "comparison": f"Write a detailed comparison article for someone searching '{keyword}'. Compare 3-4 top options with a clear recommendation. At least 1800 words.",
            "best_of_list": f"Write a 'Best X' style article for someone searching '{keyword}'. Cover 7-10 options with clear descriptions, pros/cons, and buying advice. At least 2000 words.",
            "how_to_guide": f"Write a practical how-to guide for someone searching '{keyword}'. Include step-by-step instructions and naturally recommend relevant tools/products. At least 1500 words.",
            "buyer_guide": f"Write a comprehensive buyer's guide for someone searching '{keyword}'. Include what to look for, top recommendations, and FAQs. At least 1800 words.",
        }

        prompt = f"""Niche: {niche['name']}
Target keyword: "{keyword}"
Content type: {content_type}
{product_info}

{type_instructions.get(content_type, type_instructions['buyer_guide'])}

Format your response as JSON:
{{
  "title": "SEO-optimized title (include keyword)",
  "meta_description": "Compelling meta description 150-160 chars with keyword",
  "slug": "url-friendly-slug",
  "secondary_keywords": ["related keyword 1", "related keyword 2", "related keyword 3"],
  "body": "Full markdown article content here...",
  "word_count": <estimated word count integer>
}}

The body must:
- Use H2 and H3 headings naturally
- Include the primary keyword in the first paragraph and naturally throughout
- Have a clear CTA section near the end
- Be genuinely helpful — readers should learn something valuable
- Include [AFFILIATE_LINK] placeholder where products should be linked"""

        try:
            result = self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=8192)
            result["content_type"] = content_type
            result["target_keyword"] = keyword
            return result
        except Exception as e:
            logger.error(f"Content creation failed for keyword '{keyword}': {e}")
            return None

    def _save_content(self, piece: dict, niche_id: int):
        slug = piece.get("slug", "")
        if not slug:
            slug = re.sub(r"[^a-z0-9]+", "-", piece.get("title", "untitled").lower()).strip("-")

        # Ensure slug uniqueness
        slug = f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        with get_db() as db:
            content = ContentPiece(
                niche_id=niche_id,
                title=piece.get("title", "Untitled")[:299],
                slug=slug[:299],
                content_type=piece.get("content_type", "blog_post"),
                body=piece.get("body", ""),
                meta_description=piece.get("meta_description", "")[:159],
                target_keyword=piece.get("target_keyword", "")[:199],
                secondary_keywords=piece.get("secondary_keywords", []),
                word_count=piece.get("word_count", 0),
                status=ContentStatus.draft,
            )
            db.add(content)

    def create_single_review(self, product_name: str, niche: str) -> dict:
        """Create a review for a specific product."""
        prompt = f"""Write a comprehensive, honest affiliate product review for: "{product_name}" in the "{niche}" niche.

Include: Overview, Key Features, Pros, Cons, Who It's For, Pricing, Alternatives, Verdict.

Return JSON:
{{
  "title": "title with product name",
  "meta_description": "meta description",
  "slug": "slug",
  "secondary_keywords": [],
  "body": "full markdown review",
  "word_count": 1800
}}"""
        try:
            result = self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=6000)
            result["content_type"] = "product_review"
            result["target_keyword"] = f"{product_name} review"
            return result
        except Exception as e:
            logger.error(f"Review creation failed: {e}")
            return {}
