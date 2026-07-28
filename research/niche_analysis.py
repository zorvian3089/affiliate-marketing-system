"""
Deep ClickBank Niche Analysis
Run this standalone to get a full ranked niche report.
python research/niche_analysis.py
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """You are a veteran ClickBank affiliate marketer with 10+ years experience.
You have deep knowledge of gravity scores, conversion rates, refund rates, and which niches
consistently produce income for affiliates. Be brutally honest and data-driven.
Respond only in valid JSON."""

class NicheAnalyzer(BaseAgent):
    name = "NicheAnalyzer"

    def execute(self, **kwargs):
        return self.full_analysis()

    def full_analysis(self):
        prompt = """Analyze ALL major ClickBank niches for affiliate marketing profitability in 2025-2026.

For each niche provide REAL data based on typical ClickBank marketplace patterns.

Return JSON array sorted by total_score descending:
[
  {
    "rank": 1,
    "niche": "niche name",
    "category": "Health|Wealth|Relationships|Lifestyle|Survival",
    "avg_gravity": <typical gravity score 0-500>,
    "avg_commission_percent": <typical commission %>,
    "avg_product_price": <typical product price USD>,
    "avg_commission_usd": <avg commission per sale USD>,
    "monthly_search_volume": <Google searches/month estimate>,
    "competition": "low|medium|high|very_high",
    "seo_difficulty": "easy|medium|hard|very_hard",
    "buyer_intent": "low|medium|high|very_high",
    "refund_rate": "low|medium|high",
    "evergreen": true/false,
    "top_products": ["Product Name 1", "Product Name 2", "Product Name 3"],
    "best_keywords": ["keyword 1", "keyword 2", "keyword 3", "keyword 4", "keyword 5"],
    "best_content_types": ["review", "comparison", "listicle", "how-to"],
    "traffic_sources": ["seo", "pinterest", "youtube", "email", "reddit"],
    "why_profitable": "1-2 sentence explanation",
    "biggest_risk": "main challenge for affiliates",
    "time_to_first_commission_days": <realistic estimate>,
    "monthly_income_potential_6months": <USD realistic for new affiliate>,
    "total_score": <0-100 composite score>
  }
]

Cover ALL these niches:
- Weight loss / fat burning
- Diabetes / blood sugar
- Keto diet
- Muscle building / bodybuilding
- Joint pain / arthritis
- Anxiety / stress / sleep
- Make money online / affiliate marketing
- Forex / crypto trading
- Manifestation / law of attraction
- Relationship / dating (men)
- Relationship / dating (women)
- Survival / prepping
- Dog training
- Cat health
- Gardening / homesteading
- Solar / off-grid
- Golf improvement
- Tinnitus / hearing
- Vision / eyesight
- Memory / brain health

Include all 20."""

        return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=8000)


if __name__ == "__main__":
    analyzer = NicheAnalyzer()
    print("Analyzing all ClickBank niches... (this takes ~30 seconds)")
    results = analyzer.full_analysis()

    print("\n" + "="*80)
    print("CLICKBANK NICHE ANALYSIS — RANKED BY PROFITABILITY")
    print("="*80)

    for n in results:
        print(f"\n#{n['rank']} {n['niche'].upper()} [{n['category']}]")
        print(f"  Score: {n['total_score']}/100 | Commission: ${n['avg_commission_usd']}/sale ({n['avg_commission_percent']}%)")
        print(f"  Gravity: {n['avg_gravity']} | Price: ${n['avg_product_price']} | Competition: {n['competition']}")
        print(f"  Time to first $: ~{n['time_to_first_commission_days']} days")
        print(f"  6-month income potential: ${n['monthly_income_potential_6months']}/month")
        print(f"  Why: {n['why_profitable']}")
        print(f"  Risk: {n['biggest_risk']}")
        print(f"  Top products: {', '.join(n['top_products'][:3])}")
        print(f"  Best keywords: {', '.join(n['best_keywords'][:3])}")

    # Save to file
    with open("research/niche_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nFull report saved to research/niche_report.json")
    print(f"Total niches analyzed: {len(results)}")
    top5 = [n['niche'] for n in results[:5]]
    print(f"TOP 5 to target: {', '.join(top5)}")
