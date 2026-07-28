"""
SEO Agent
Handles keyword research, on-page optimization, internal linking,
and generates SEO reports for published content.
"""
import logging
import requests
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, Niche
from config.settings import SERP_API_KEY, GOOGLE_SEARCH_API_KEY, GOOGLE_CSE_ID

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert SEO strategist specializing in affiliate marketing sites.
You understand:
- Keyword research and search intent
- On-page SEO optimization
- Content gap analysis
- Internal linking strategy
- Technical SEO fundamentals

Always respond with valid JSON only."""


class SEOAgent(BaseAgent):
    name = "SEOAgent"

    def execute(self, **kwargs) -> dict:
        # Run full SEO audit cycle
        keywords = self._research_keywords()
        optimized = self._optimize_existing_content()
        linking = self._generate_internal_links()
        return {
            "keywords_found": len(keywords),
            "content_optimized": optimized,
            "internal_links_added": linking,
        }

    def research_keywords(self, niche: str, seed_keywords: list[str]) -> list[dict]:
        """Find profitable keywords for a niche."""
        prompt = f"""Niche: {niche}
Seed keywords: {', '.join(seed_keywords[:5])}

Perform keyword research and return 20 target keywords.

Return JSON array:
[
  {{
    "keyword": "exact keyword phrase",
    "monthly_searches": <integer estimate>,
    "competition": "low|medium|high",
    "intent": "informational|commercial|transactional|navigational",
    "difficulty_score": <0-100, lower is easier>,
    "cpc_estimate": <USD float>,
    "content_type": "review|comparison|guide|listicle",
    "priority": "high|medium|low"
  }}
]

Prioritize:
- Long-tail keywords (3-5 words) with buyer intent
- Low competition, reasonable search volume
- Keywords that signal purchase intent: best, review, vs, buy, cheap, discount"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=3000)
        except Exception as e:
            logger.error(f"Keyword research failed: {e}")
            return []

    def _research_keywords(self) -> list[dict]:
        with get_db() as db:
            niches = db.query(Niche).filter(Niche.status.in_(["active", "testing"])).all()
            niche_data = [{"name": n.name, "keywords": n.keywords or []} for n in niches]

        all_keywords = []
        for niche in niche_data:
            kws = self.research_keywords(niche["name"], niche["keywords"][:5])
            all_keywords.extend(kws)
        return all_keywords

    def optimize_content(self, content: ContentPiece) -> dict:
        """Analyze and suggest improvements for a content piece."""
        prompt = f"""Analyze this affiliate article for SEO optimization:

Title: {content.title}
Target keyword: {content.target_keyword}
Word count: {content.word_count}
Content preview (first 500 chars): {(content.body or '')[:500]}

Return JSON with optimization suggestions:
{{
  "seo_score": <0-100>,
  "title_optimized": true/false,
  "title_suggestion": "improved title if needed",
  "meta_description_suggestion": "optimized meta description",
  "h2_suggestions": ["H2 heading to add or improve"],
  "missing_keywords": ["keyword variations to include"],
  "internal_link_opportunities": ["topics to link to internally"],
  "content_gaps": ["topics readers would also want to know"],
  "cta_suggestion": "call to action text suggestion",
  "readability_score": <0-100>,
  "improvements": ["specific actionable improvement 1", "improvement 2", "improvement 3"]
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Content optimization failed: {e}")
            return {}

    def _optimize_existing_content(self) -> int:
        with get_db() as db:
            pieces = db.query(ContentPiece).filter(
                ContentPiece.status == "published",
                ContentPiece.seo_score.is_(None)
            ).limit(10).all()
            pieces_data = [
                {"id": p.id, "title": p.title, "body": p.body,
                 "target_keyword": p.target_keyword, "word_count": p.word_count}
                for p in pieces
            ]

        optimized = 0
        for piece_data in pieces_data:
            result = self._optimize_single(piece_data)
            if result:
                with get_db() as db:
                    piece = db.query(ContentPiece).filter(ContentPiece.id == piece_data["id"]).first()
                    if piece:
                        piece.seo_score = result.get("seo_score", 0)
                optimized += 1
        return optimized

    def _optimize_single(self, piece_data: dict) -> dict:
        prompt = f"""SEO score and quick audit:
Title: {piece_data['title']}
Keyword: {piece_data.get('target_keyword', '')}
Words: {piece_data.get('word_count', 0)}

Return JSON: {{"seo_score": <0-100>, "top_issue": "main thing to fix"}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=200)
        except Exception:
            return {}

    def _generate_internal_links(self) -> int:
        """Suggest internal linking between content pieces."""
        with get_db() as db:
            pieces = db.query(ContentPiece).filter(
                ContentPiece.status == "published"
            ).order_by(ContentPiece.views.desc()).limit(20).all()
            pieces_data = [{"title": p.title, "slug": p.slug, "keyword": p.target_keyword} for p in pieces]

        if len(pieces_data) < 2:
            return 0

        prompt = f"""Given these published articles, suggest internal linking opportunities:

{chr(10).join([f"- {p['title']} (/{p['slug']})" for p in pieces_data])}

Return JSON array of link suggestions:
[
  {{
    "from_article": "source article title",
    "to_article": "target article title",
    "anchor_text": "natural anchor text",
    "reason": "why this link makes sense"
  }}
]

Suggest 10 high-value internal links that improve topical authority."""
        try:
            suggestions = self.ask_claude_json(SYSTEM_PROMPT, prompt)
            return len(suggestions) if isinstance(suggestions, list) else 0
        except Exception as e:
            logger.error(f"Internal link generation failed: {e}")
            return 0

    def generate_topic_cluster(self, pillar_topic: str, niche: str) -> dict:
        """Generate a topic cluster strategy around a pillar topic."""
        prompt = f"""Create a topic cluster strategy for affiliate marketing:
Pillar topic: "{pillar_topic}"
Niche: "{niche}"

Return JSON:
{{
  "pillar_page": {{
    "title": "pillar page title",
    "keyword": "main keyword",
    "word_count_target": 4000
  }},
  "cluster_pages": [
    {{"title": "cluster page title", "keyword": "keyword", "word_count_target": 1500}}
  ],
  "internal_link_strategy": "description of how pages link together",
  "estimated_traffic_potential": <monthly visits estimate>,
  "time_to_rank_months": <estimate>
}}

Include 8-10 cluster pages."""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Topic cluster generation failed: {e}")
            return {}
