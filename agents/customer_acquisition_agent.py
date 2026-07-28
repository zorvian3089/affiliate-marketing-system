"""
Customer Acquisition Agent
Generates content for every traffic channel to bring buyers.
Covers: SEO, Quora, YouTube scripts, Pinterest, Reddit, Email lead magnets.
"""
import logging
from agents.base_agent import BaseAgent
from agents.clickbank_agent import ClickBankAgent, CLICKBANK_TOP_PRODUCTS
from database.database import get_db
from database.models import ContentPiece, Niche, ContentStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert affiliate marketing customer acquisition specialist.
You know exactly what content brings buyers — not just readers.
You understand buyer psychology, search intent, and platform-specific content strategies.
Every piece of content you create is designed to get people to click and buy.
Respond with valid JSON only."""


class CustomerAcquisitionAgent(BaseAgent):
    name = "CustomerAcquisitionAgent"

    def execute(self, **kwargs) -> dict:
        results = {}
        results["seo_articles"] = self._create_seo_buyer_content()
        results["quora_answers"] = self._create_quora_answers()
        results["youtube_scripts"] = self._create_youtube_scripts()
        results["email_lead_magnets"] = self._create_lead_magnets()
        return results

    # ── SEO Buyer Intent Content ───────────────────────────────────────────────

    def _create_seo_buyer_content(self) -> int:
        """Create high-buyer-intent articles for each niche+product combo."""
        created = 0
        cb = ClickBankAgent()

        # Best buyer intent keyword templates per product
        keyword_templates = [
            "{product} review — does it really work?",
            "{product} honest review {year}",
            "is {product} a scam or legit?",
            "{product} before and after results",
            "best {niche} supplements {year}",
            "{product} ingredients side effects",
            "where to buy {product} cheapest price",
            "{product} vs competitors",
        ]

        for product in CLICKBANK_TOP_PRODUCTS[:10]:  # Top 10 products first
            keyword = f"{product['name']} review — does it really work?"
            article = self._write_seo_article(product, keyword)
            if article:
                self._save_article(article, product["niche"])
                created += 1

        return created

    # Verified encrypted hoplinks under shanmugap account
    ENCRYPTED_HOPLINKS = {
        "jointgen":  "https://b5f4bnw7xlx9ol74p5ymq6tuf8.hop.clickbank.net",
        "javaburn":  "https://45ac8nryoc61fg08luqaycxi1a.hop.clickbank.net",
        "resurge":   "https://45ac8nryoc61fg08luqaycxi1a.hop.clickbank.net",
    }
    _FALLBACK_LINK = "https://b5f4bnw7xlx9ol74p5ymq6tuf8.hop.clickbank.net"

    def _write_seo_article(self, product: dict, keyword: str) -> dict | None:
        hoplink = self.ENCRYPTED_HOPLINKS.get(product["vendor_id"], self._FALLBACK_LINK)

        prompt = f"""Write a complete SEO affiliate review article.

Product: {product['name']}
Target keyword: "{keyword}"
Price: ${product['price']}
Commission: {product['commission_rate']}%
Description: {product['description']}
Pros: {', '.join(product['pros'])}
Cons: {', '.join(product['cons'])}
Affiliate link: {hoplink}

Write a 1800-word honest review that:
1. Ranks for "{keyword}" on Google
2. Answers the reader's real question (does this work?)
3. Builds trust with honest pros AND cons
4. Naturally includes the affiliate link 2-3 times
5. Has a clear verdict and recommendation

Return JSON:
{{
  "title": "SEO title with keyword",
  "meta_description": "compelling meta description 150 chars",
  "slug": "url-slug",
  "body": "full markdown article with ## headings, the affiliate link placed naturally as [Click here to visit {product['name']} official site]({hoplink}) — IMPORTANT: always close markdown links with )",
  "word_count": 1800,
  "target_keyword": "{keyword}",
  "secondary_keywords": ["related keyword 1", "related keyword 2", "related keyword 3"]
}}"""
        try:
            result = self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=6000)
            result["content_type"] = "product_review"
            result["product_name"] = product["name"]
            result["hoplink"] = hoplink
            return result
        except Exception as e:
            logger.error(f"SEO article failed for {product['name']}: {e}")
            return None

    def _save_article(self, article: dict, niche_name: str):
        import re
        from datetime import datetime
        with get_db() as db:
            niche = db.query(Niche).filter(Niche.name == niche_name).first()
            if not niche:
                niche = Niche(name=niche_name, keywords=[], status="active")
                db.add(niche)
                db.flush()

            slug = article.get("slug", "")
            if not slug:
                slug = re.sub(r"[^a-z0-9]+", "-", article.get("title", "article").lower()).strip("-")
            slug = f"{slug}-{datetime.utcnow().strftime('%H%M%S')}"

            piece = ContentPiece(
                niche_id=niche.id,
                title=article.get("title", "")[:299],
                slug=slug[:299],
                content_type=article.get("content_type", "product_review"),
                body=article.get("body", ""),
                meta_description=article.get("meta_description", "")[:159],
                target_keyword=article.get("target_keyword", "")[:199],
                secondary_keywords=article.get("secondary_keywords", []),
                word_count=article.get("word_count", 0),
                status=ContentStatus.draft,
            )
            db.add(piece)

    # ── Quora Answers ──────────────────────────────────────────────────────────

    def _create_quora_answers(self) -> int:
        """Generate Quora answers that drive traffic to affiliate content."""
        prompt = """Generate 10 Quora answer templates for affiliate marketing.
Cover these niches: weight loss, blood sugar, keto, relationships, dog training, make money online.

Each answer should:
- Directly answer the question with VALUE (not spam)
- Establish credibility naturally
- Mention a product recommendation naturally at the end
- Include a "I found this resource helpful" style link placement

Return JSON array:
[
  {
    "niche": "niche name",
    "question": "the Quora question to answer",
    "answer": "full Quora answer (300-500 words, helpful and genuine)",
    "product_mention": "how to naturally mention the product",
    "cta": "soft call to action at the end",
    "estimated_views": "questions with X monthly views get Y traffic",
    "best_subreddits": ["r/subreddit1", "r/subreddit2"]
  }
]"""
        try:
            answers = self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=6000)
            # Save as content pieces
            if isinstance(answers, list):
                for ans in answers:
                    self._save_article({
                        "title": ans.get("question", "Quora Answer"),
                        "body": ans.get("answer", ""),
                        "meta_description": ans.get("cta", "")[:159],
                        "slug": "",
                        "target_keyword": ans.get("question", ""),
                        "secondary_keywords": [],
                        "word_count": len(ans.get("answer", "").split()),
                        "content_type": "quora_answer",
                    }, ans.get("niche", "general"))
            return len(answers) if isinstance(answers, list) else 0
        except Exception as e:
            logger.error(f"Quora answer generation failed: {e}")
            return 0

    # ── YouTube Scripts ────────────────────────────────────────────────────────

    def _create_youtube_scripts(self) -> int:
        """Generate YouTube video scripts for top products."""
        scripts_created = 0
        for product in CLICKBANK_TOP_PRODUCTS[:5]:
            script = self._write_youtube_script(product)
            if script:
                self._save_article({
                    "title": script.get("video_title", ""),
                    "body": script.get("full_script", ""),
                    "meta_description": script.get("video_description", "")[:159],
                    "slug": "",
                    "target_keyword": script.get("target_keyword", ""),
                    "secondary_keywords": script.get("tags", []),
                    "word_count": len(script.get("full_script", "").split()),
                    "content_type": "youtube_script",
                }, product["niche"])
                scripts_created += 1
        return scripts_created

    def _write_youtube_script(self, product: dict) -> dict | None:
        hoplink = ClickBankAgent.build_hoplink(product["vendor_id"])
        prompt = f"""Write a YouTube video script for an affiliate review of: {product['name']}
Price: ${product['price']} | Commission: {product['commission_rate']}%
Description: {product['description']}

Return JSON:
{{
  "video_title": "YouTube title (include keyword, max 60 chars)",
  "target_keyword": "main keyword",
  "thumbnail_text": "bold text for thumbnail (5 words max)",
  "video_description": "YouTube description with affiliate link",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "full_script": "Complete word-for-word script with [HOOK], [INTRO], [PROBLEM], [SOLUTION], [REVIEW], [PROS_CONS], [CTA] sections. Affiliate link: {hoplink}",
  "duration_minutes": 8,
  "b_roll_suggestions": ["visual 1", "visual 2", "visual 3"]
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=4000)
        except Exception as e:
            logger.error(f"YouTube script failed for {product['name']}: {e}")
            return None

    # ── Lead Magnets ───────────────────────────────────────────────────────────

    def _create_lead_magnets(self) -> int:
        """Create free lead magnets to build email list."""
        prompt = """Create 5 email lead magnets for affiliate marketing niches.
These are free PDF/guide titles that make people give their email.

Return JSON array:
[
  {
    "niche": "niche name",
    "lead_magnet_title": "Free [thing] title that people WANT",
    "subtitle": "what they get",
    "content_outline": ["chapter 1", "chapter 2", "chapter 3", "chapter 4", "chapter 5"],
    "opt_in_headline": "headline for the opt-in form",
    "opt_in_subheadline": "subheadline",
    "thank_you_page_offer": "what to show immediately after signup",
    "email_sequence_angle": "what the follow-up sequence promotes"
  }
]

Niches to cover: weight loss, make money online, relationship dating women, dog training, anxiety stress sleep"""
        try:
            magnets = self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=3000)
            return len(magnets) if isinstance(magnets, list) else 0
        except Exception as e:
            logger.error(f"Lead magnet creation failed: {e}")
            return 0

    # ── Public methods for API ─────────────────────────────────────────────────

    def generate_content_for_niche(self, niche: str) -> dict:
        """Generate all content types for a specific niche."""
        products = ClickBankAgent().get_products_by_niche(niche)
        if not products:
            return {"error": f"No products found for niche: {niche}"}

        results = {
            "niche": niche,
            "seo_articles": 0,
            "quora_answers": 0,
            "youtube_scripts": 0,
        }

        for product in products[:2]:
            article = self._write_seo_article(product, f"{product['name']} review")
            if article:
                self._save_article(article, niche)
                results["seo_articles"] += 1

        return results

    def get_all_hoplinks_report(self) -> list[dict]:
        """Get all your affiliate links for reference."""
        cb = ClickBankAgent()
        return cb.get_all_hoplinks()
