"""
A/B Testing Agent
Tests headlines, CTAs, email subjects, and landing page copy.
Uses statistical significance to declare winners.
"""
import logging
import math
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, EmailCampaign

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a conversion rate optimization (CRO) expert.
You design A/B tests, interpret results, and recommend winners.
You understand statistical significance and avoid premature conclusions.
Always respond with valid JSON only."""


class ABTestingAgent(BaseAgent):
    name = "ABTestingAgent"

    def execute(self, **kwargs) -> dict:
        tests = self._generate_headline_tests()
        return {"tests_generated": len(tests)}

    def generate_headline_variants(self, original_title: str, niche: str, keyword: str) -> list[str]:
        prompt = f"""Generate 4 A/B test variants for this article headline:
Original: "{original_title}"
Niche: {niche}
Target keyword: {keyword}

Each variant should test a different copywriting angle:
1. Curiosity-driven
2. Number/list-based
3. Benefit-focused
4. Fear of missing out / urgency

Return JSON array of 4 strings: ["variant1", "variant2", "variant3", "variant4"]
Keep the target keyword in each variant."""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Headline variant generation failed: {e}")
            return []

    def generate_cta_variants(self, product_name: str, niche: str) -> list[dict]:
        prompt = f"""Generate 5 A/B test variants for a CTA button/section for: "{product_name}" in the "{niche}" niche.

Return JSON array:
[
  {{
    "button_text": "short button label",
    "surrounding_copy": "1-2 sentences around the button",
    "angle": "urgency|benefit|curiosity|social_proof|risk_reversal"
  }}
]"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"CTA variant generation failed: {e}")
            return []

    def analyze_test_results(self, control: dict, variant: dict) -> dict:
        """Analyze A/B test results and recommend winner."""
        control_rate = control["conversions"] / max(control["visitors"], 1)
        variant_rate = variant["conversions"] / max(variant["visitors"], 1)
        lift = ((variant_rate - control_rate) / max(control_rate, 0.001)) * 100
        significant = self._is_statistically_significant(
            control["visitors"], control["conversions"],
            variant["visitors"], variant["conversions"]
        )

        prompt = f"""A/B Test Results:
Control: {control['visitors']} visitors, {control['conversions']} conversions ({control_rate:.2%} rate)
Variant: {variant['visitors']} visitors, {variant['conversions']} conversions ({variant_rate:.2%} rate)
Lift: {lift:.1f}%
Statistically significant: {significant}

Control description: {control.get('description', 'original')}
Variant description: {variant.get('description', 'test variant')}

Return JSON:
{{
  "winner": "control|variant|inconclusive",
  "confidence_level": "high|medium|low",
  "recommendation": "implement variant|keep control|run longer|test needed",
  "next_test_suggestion": "what to test next",
  "insights": "what this result tells us about the audience"
}}"""
        try:
            result = self.ask_claude_json(SYSTEM_PROMPT, prompt)
            result["lift_percent"] = round(lift, 1)
            result["statistically_significant"] = significant
            return result
        except Exception as e:
            logger.error(f"Test analysis failed: {e}")
            return {"winner": "inconclusive", "error": str(e)}

    def _is_statistically_significant(self, n1: int, c1: int, n2: int, c2: int,
                                       threshold: float = 0.95) -> bool:
        """Chi-squared test for statistical significance."""
        if n1 < 100 or n2 < 100:
            return False
        p1 = c1 / n1
        p2 = c2 / n2
        p_pool = (c1 + c2) / (n1 + n2)
        if p_pool == 0 or p_pool == 1:
            return False
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return False
        z = abs(p1 - p2) / se
        # z > 1.96 = 95% confidence
        return z > 1.96

    def _generate_headline_tests(self) -> list:
        with get_db() as db:
            # Find published content with decent traffic
            pieces = db.query(ContentPiece).filter(
                ContentPiece.status == "published",
                ContentPiece.views >= 100,
            ).limit(5).all()
            return [{"id": p.id, "title": p.title} for p in pieces]

    def create_email_subject_test(self, topic: str, niche: str) -> dict:
        """Generate email subject line A/B test."""
        prompt = f"""Create an email subject line A/B test for topic: "{topic}" in niche: "{niche}"

Return JSON:
{{
  "control": {{
    "subject": "original subject",
    "angle": "description of approach"
  }},
  "variant_a": {{
    "subject": "test subject A",
    "angle": "description of approach"
  }},
  "variant_b": {{
    "subject": "test subject B",
    "angle": "description of approach"
  }},
  "what_we_are_testing": "what variable is being isolated",
  "success_metric": "open_rate|click_rate|revenue",
  "recommended_sample_size": <min subscribers per variant>
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Email subject test creation failed: {e}")
            return {}
