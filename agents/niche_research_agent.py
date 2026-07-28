"""
Niche Research Agent
Analyzes niches for profitability, competition, and affiliate opportunity.
Outputs ranked niches with keywords to target.
"""
import json
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import Niche, NicheStatus
from config.settings import SERP_API_KEY, TARGET_NICHES

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert affiliate marketing niche researcher.
You analyze niches for:
- Search volume and trend momentum
- Affiliate commission potential (programs available, rates)
- Buyer intent keywords
- Competition level (low = easier to rank)
- Seasonal vs evergreen demand

Always respond with valid JSON only. No markdown, no explanation outside JSON."""


class NicheResearchAgent(BaseAgent):
    name = "NicheResearchAgent"

    def execute(self, niches: list[str] | None = None, **kwargs) -> dict:
        niches = niches or TARGET_NICHES
        results = []

        for niche in niches:
            logger.info(f"Researching niche: {niche}")
            analysis = self._analyze_niche(niche)
            if analysis:
                self._save_niche(niche, analysis)
                results.append({"niche": niche, "analysis": analysis})

        ranked = self._rank_niches(results)
        return {"niches_analyzed": len(results), "top_niches": ranked[:5]}

    def _analyze_niche(self, niche: str) -> dict | None:
        prompt = f"""Analyze this affiliate marketing niche: "{niche}"

Return JSON with this exact structure:
{{
  "competition_score": <0-100 float, lower = easier>,
  "monthly_searches": <estimated monthly searches integer>,
  "avg_commission_rate": <typical commission % float>,
  "buyer_intent_score": <0-100, how likely searchers buy>,
  "evergreen": <true/false>,
  "top_affiliate_programs": ["program1", "program2", "program3"],
  "seed_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "long_tail_opportunities": ["long tail 1", "long tail 2", "long tail 3"],
  "content_angles": ["angle1", "angle2", "angle3"],
  "estimated_monthly_revenue_potential": <USD float for a new site after 6 months>,
  "notes": "brief strategic notes"
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Failed to analyze niche {niche}: {e}")
            return None

    def _save_niche(self, niche_name: str, analysis: dict):
        with get_db() as db:
            existing = db.query(Niche).filter(Niche.name == niche_name).first()
            if existing:
                existing.keywords = analysis.get("seed_keywords", []) + analysis.get("long_tail_opportunities", [])
                existing.competition_score = analysis.get("competition_score")
                existing.monthly_searches = analysis.get("monthly_searches")
                existing.avg_commission_rate = analysis.get("avg_commission_rate")
                existing.notes = json.dumps({
                    "buyer_intent_score": analysis.get("buyer_intent_score"),
                    "evergreen": analysis.get("evergreen"),
                    "top_affiliate_programs": analysis.get("top_affiliate_programs"),
                    "content_angles": analysis.get("content_angles"),
                    "revenue_potential": analysis.get("estimated_monthly_revenue_potential"),
                    "notes": analysis.get("notes"),
                })
                existing.updated_at = datetime.utcnow()
            else:
                n = Niche(
                    name=niche_name,
                    keywords=analysis.get("seed_keywords", []) + analysis.get("long_tail_opportunities", []),
                    competition_score=analysis.get("competition_score"),
                    monthly_searches=analysis.get("monthly_searches"),
                    avg_commission_rate=analysis.get("avg_commission_rate"),
                    status=NicheStatus.testing,
                    notes=json.dumps({
                        "buyer_intent_score": analysis.get("buyer_intent_score"),
                        "evergreen": analysis.get("evergreen"),
                        "top_affiliate_programs": analysis.get("top_affiliate_programs"),
                        "content_angles": analysis.get("content_angles"),
                        "revenue_potential": analysis.get("estimated_monthly_revenue_potential"),
                        "notes": analysis.get("notes"),
                    }),
                )
                db.add(n)

    def _rank_niches(self, results: list[dict]) -> list[dict]:
        """Score = high revenue potential + low competition + high buyer intent."""
        scored = []
        for item in results:
            a = item["analysis"]
            if not a:
                continue
            score = (
                (a.get("estimated_monthly_revenue_potential", 0) / 1000) * 0.4
                + (100 - a.get("competition_score", 50)) * 0.35
                + a.get("buyer_intent_score", 50) * 0.25
            )
            scored.append({"niche": item["niche"], "score": round(score, 2), **a})
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def get_keyword_ideas(self, niche: str, seed_keyword: str) -> list[str]:
        """Generate long-tail keyword ideas for a niche."""
        prompt = f"""Generate 20 long-tail buyer-intent keywords for affiliate marketing in the "{niche}" niche, starting from seed keyword: "{seed_keyword}".

Focus on keywords with:
- Buying intent ("best", "review", "buy", "vs", "discount", "cheap", "top")
- Informational intent that leads to purchases ("how to", "guide")

Return JSON array of strings only: ["keyword1", "keyword2", ...]"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            return []
