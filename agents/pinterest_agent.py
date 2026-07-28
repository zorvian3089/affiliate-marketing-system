"""
Pinterest Agent
Pinterest drives massive FREE traffic to affiliate content — especially for
health, weight loss, recipes, home, relationships, and lifestyle niches.
Pins have a 4-month average lifespan vs 18 minutes on Twitter.
"""
import logging
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Pinterest marketing expert for affiliate marketing.
Pinterest is a search engine, not social media. People come with buying intent.
You create pins that:
- Show up in Pinterest search results
- Drive clicks to affiliate content
- Use keyword-rich descriptions
- Appeal to emotions and aspirations
- Have clear value propositions

Always respond with valid JSON only."""


class PinterestAgent(BaseAgent):
    name = "PinterestAgent"

    # Top performing Pinterest niches (research-backed)
    HIGH_VALUE_NICHES = [
        "weight loss", "keto diet", "manifestation", "relationship dating women",
        "gardening homesteading", "cat health", "dog training", "anxiety stress sleep"
    ]

    def execute(self, **kwargs) -> dict:
        pins_created = 0
        with get_db() as db:
            content_list = db.query(ContentPiece).filter(
                ContentPiece.status == "published",
                ContentPiece.published_url.isnot(None),
            ).order_by(ContentPiece.created_at.desc()).limit(10).all()
            content_data = [
                {"id": c.id, "title": c.title, "meta": c.meta_description,
                 "keyword": c.target_keyword, "url": c.published_url}
                for c in content_list
            ]

        for content in content_data:
            pin_data = self._create_pin(content)
            if pin_data:
                self._save_pin(pin_data, content["id"])
                pins_created += 1

        # Also create standalone pins for high-traffic keywords
        idea_pins = self._create_idea_pins()
        return {"pins_created": pins_created, "idea_pins": idea_pins}

    def _create_pin(self, content: dict) -> dict | None:
        prompt = f"""Create a Pinterest pin for this affiliate content:

Title: {content['title']}
URL: {content['url']}
Description: {content.get('meta', '')}
Keyword: {content.get('keyword', '')}

Return JSON:
{{
  "pin_title": "SEO-optimized pin title (max 100 chars, include keyword)",
  "pin_description": "keyword-rich description 150-300 chars — what will they learn/get? End with soft CTA",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "board_name": "which Pinterest board to post to",
  "image_text_overlay": "bold text to overlay on pin image (max 8 words)",
  "image_concept": "describe the ideal pin image for a graphic designer",
  "best_time": "morning|afternoon|evening",
  "click_bait_hook": "curiosity-driven first sentence to make people stop scrolling"
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Pin creation failed: {e}")
            return None

    def _save_pin(self, pin_data: dict, content_id: int):
        scheduled = datetime.utcnow() + timedelta(hours=2)
        with get_db() as db:
            post = SocialPost(
                content_id=content_id,
                platform="pinterest",
                post_text=f"{pin_data.get('pin_title', '')}\n\n{pin_data.get('pin_description', '')}",
                hashtags=pin_data.get("hashtags", []),
                scheduled_at=scheduled,
                status="scheduled",
            )
            db.add(post)

    def _create_idea_pins(self) -> int:
        """Create standalone idea pins for top keywords (no blog post needed)."""
        prompt = """Create 5 Pinterest Idea Pin concepts for affiliate marketing in these niches:
weight loss, keto diet, manifestation, relationship advice, dog training.

These are standalone pins that provide VALUE without needing to click away.
They build followers and brand trust.

Return JSON array:
[
  {
    "niche": "niche name",
    "concept": "pin concept title",
    "slides": ["slide 1 text", "slide 2 text", "slide 3 text", "slide 4 text"],
    "cta_slide": "final slide text with soft CTA",
    "product_to_link": "type of affiliate product to link in bio",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
  }
]"""
        try:
            ideas = self.ask_claude_json(SYSTEM_PROMPT, prompt)
            return len(ideas) if isinstance(ideas, list) else 0
        except Exception as e:
            logger.error(f"Idea pin creation failed: {e}")
            return 0

    def generate_board_strategy(self) -> dict:
        """Generate a complete Pinterest board strategy."""
        prompt = """Create a Pinterest board strategy for an affiliate marketer targeting multiple niches.

Return JSON:
{
  "boards": [
    {
      "name": "board name",
      "niche": "target niche",
      "description": "board description with keywords",
      "target_audience": "who follows this board",
      "pin_frequency": "X pins per day",
      "affiliate_products": ["type of product 1", "type of product 2"],
      "top_keywords": ["keyword1", "keyword2", "keyword3"]
    }
  ],
  "profile_bio": "Pinterest bio with keywords (160 chars)",
  "posting_schedule": "optimal posting times and frequency",
  "growth_strategy": "how to grow to 10k followers in 90 days"
}

Include 8-10 boards covering all major affiliate niches."""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=3000)
        except Exception as e:
            logger.error(f"Board strategy generation failed: {e}")
            return {}

    def generate_pin_templates(self, niche: str, count: int = 10) -> list[dict]:
        """Generate ready-to-use pin templates for a niche."""
        prompt = f"""Generate {count} Pinterest pin templates for the "{niche}" niche.
Each should be a complete, ready-to-post pin.

Return JSON array:
[
  {{
    "title": "pin title",
    "description": "pin description with keywords",
    "image_text": "overlay text for image (bold, short)",
    "image_style": "infographic|before-after|quote|tips-list|product",
    "hashtags": ["#tag1", "#tag2", "#tag3"],
    "affiliate_angle": "what product to promote with this pin"
  }}
]"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=4000)
        except Exception as e:
            logger.error(f"Pin template generation failed: {e}")
            return []
