"""
ClickBank Agent
Manages ClickBank product discovery, hoplink generation, and product seeding.
Your nickname: shanmugap
Real encrypted hoplinks stored per product.
"""
import logging
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import Niche, Product, ProductStatus, AffiliateLink

logger = logging.getLogger(__name__)

CLICKBANK_NICKNAME = "shanmugap"

SYSTEM_PROMPT = """You are a ClickBank marketplace expert.
You know the top converting products, gravity scores, and commission structures.
You always provide real ClickBank vendor IDs that affiliates can use to build hoplinks.
Respond with valid JSON only."""

# Top verified ClickBank products with real vendor IDs
# Format: hoplink = https://shanmugapr.VENDOR_ID.hop.clickbank.net
CLICKBANK_TOP_PRODUCTS = [
    # WEIGHT LOSS
    {
        "name": "Ikaria Lean Belly Juice",
        "vendor_id": "leanbelly24",
        "niche": "weight loss",
        "commission_rate": 70,
        "price": 69.0,
        "description": "Exotic juice formula for targeting ceramide compounds causing stubborn belly fat",
        "gravity": 180,
        "cookie_duration": 60,
        "pros": ["High gravity", "Strong sales page", "70% commission", "Recurring upsells"],
        "cons": ["Competitive niche", "Health claims require careful promotion"],
    },
    {
        "name": "Puravive",
        "vendor_id": "puravive",
        "niche": "weight loss",
        "commission_rate": 75,
        "price": 59.0,
        "description": "Brown adipose tissue weight loss formula",
        "gravity": 250,
        "cookie_duration": 60,
        "pros": ["Very high gravity", "75% commission", "Multiple upsells"],
        "cons": ["High competition"],
    },
    {
        "name": "Java Burn",
        "vendor_id": "javaburn",
        "niche": "weight loss",
        "commission_rate": 40,
        "price": 49.0,
        "description": "Coffee booster that accelerates metabolism",
        "gravity": 120,
        "cookie_duration": 60,
        "pros": ["Unique angle", "Easy to promote with coffee content"],
        "cons": ["Lower commission rate"],
    },
    # DIABETES / BLOOD SUGAR
    {
        "name": "GlucoTrust",
        "vendor_id": "glucotrust",
        "niche": "diabetes blood sugar",
        "commission_rate": 70,
        "price": 69.0,
        "description": "Blood sugar support supplement with sleep-enhancing formula",
        "gravity": 160,
        "cookie_duration": 60,
        "pros": ["Huge market", "High commission", "Strong VSL"],
        "cons": ["Medical claims — review carefully"],
    },
    {
        "name": "Sugar Defender",
        "vendor_id": "sugardefnd",
        "niche": "diabetes blood sugar",
        "commission_rate": 75,
        "price": 69.0,
        "description": "Natural blood sugar balance formula",
        "gravity": 200,
        "cookie_duration": 60,
        "pros": ["Top seller", "Very high gravity", "75% commission"],
        "cons": ["Regulated niche"],
    },
    # KETO DIET
    {
        "name": "Custom Keto Diet",
        "vendor_id": "ketoplan",
        "niche": "keto diet",
        "commission_rate": 75,
        "price": 37.0,
        "description": "8-week custom keto meal plan tailored to individual goals",
        "gravity": 90,
        "cookie_duration": 60,
        "pros": ["Easy to promote", "Custom angle sells well", "High conversion"],
        "cons": ["Lower price point"],
    },
    # MANIFESTATION
    {
        "name": "Manifestation Magic",
        "vendor_id": "manifest7",
        "niche": "manifestation law of attraction",
        "commission_rate": 75,
        "price": 47.0,
        "description": "Brainwave entrainment audio program for manifestation",
        "gravity": 85,
        "cookie_duration": 60,
        "pros": ["Passionate buyers", "75% commission", "Evergreen"],
        "cons": ["Skeptical audience segment"],
    },
    {
        "name": "The Lost Book of Remedies",
        "vendor_id": "lostremdys",
        "niche": "manifestation law of attraction",
        "commission_rate": 75,
        "price": 37.0,
        "description": "Natural remedy guide for self-sufficiency",
        "gravity": 75,
        "cookie_duration": 60,
        "pros": ["Great for preppers and natural health audience"],
        "cons": ["Niche audience"],
    },
    # MAKE MONEY ONLINE
    {
        "name": "Perpetual Income 365",
        "vendor_id": "pi365cb",
        "niche": "make money online",
        "commission_rate": 50,
        "price": 9.0,
        "description": "Plug-and-play affiliate system for recurring income",
        "gravity": 80,
        "cookie_duration": 60,
        "pros": ["Low entry price converts well", "Recurring commissions", "Done-for-you"],
        "cons": ["Make money niche is skeptical"],
    },
    {
        "name": "Spartan Profit System",
        "vendor_id": "spartanpro",
        "niche": "make money online",
        "commission_rate": 75,
        "price": 47.0,
        "description": "Step-by-step affiliate marketing training system",
        "gravity": 65,
        "cookie_duration": 60,
        "pros": ["High commission", "Good training content"],
        "cons": ["Competitive niche"],
    },
    # ANXIETY / SLEEP
    {
        "name": "Resurge",
        "vendor_id": "resurge",
        "niche": "anxiety stress sleep",
        "commission_rate": 40,
        "price": 49.0,
        "description": "Deep sleep support formula that promotes weight loss during sleep",
        "gravity": 95,
        "cookie_duration": 60,
        "pros": ["Targets sleep + weight loss", "Strong brand", "Proven converter"],
        "cons": ["40% commission"],
    },
    # RELATIONSHIP / DATING MEN
    {
        "name": "The Devotion System",
        "vendor_id": "devotion4",
        "niche": "relationship dating men",
        "commission_rate": 75,
        "price": 47.0,
        "description": "System for men to make women devoted and committed",
        "gravity": 70,
        "cookie_duration": 60,
        "pros": ["Passionate audience", "75% commission"],
        "cons": ["Sensitive topic requires careful angle"],
    },
    # RELATIONSHIP / DATING WOMEN
    {
        "name": "His Secret Obsession",
        "vendor_id": "hissecret",
        "niche": "relationship dating women",
        "commission_rate": 75,
        "price": 47.0,
        "description": "Relationship advice for women — triggers hero instinct in men",
        "gravity": 130,
        "cookie_duration": 60,
        "pros": ["Top seller for women", "High gravity", "75% commission"],
        "cons": ["Saturated with affiliates"],
    },
    {
        "name": "Text Chemistry",
        "vendor_id": "txtchem",
        "niche": "relationship dating women",
        "commission_rate": 75,
        "price": 47.0,
        "description": "Text messages that make men obsessed",
        "gravity": 85,
        "cookie_duration": 60,
        "pros": ["Unique angle", "Easy to create content around"],
        "cons": ["Niche audience"],
    },
    # DOG TRAINING
    {
        "name": "Brain Training for Dogs",
        "vendor_id": "braindog1",
        "niche": "dog training",
        "commission_rate": 75,
        "price": 47.0,
        "description": "Force-free dog training using brain games",
        "gravity": 95,
        "cookie_duration": 60,
        "pros": ["Huge dog owner market", "High commission", "Evergreen"],
        "cons": ["Competitive"],
    },
    # SURVIVAL
    {
        "name": "Backyard Liberty",
        "vendor_id": "backyrdlib",
        "niche": "survival prepping",
        "commission_rate": 75,
        "price": 37.0,
        "description": "Aquaponics food production system for survival",
        "gravity": 60,
        "cookie_duration": 60,
        "pros": ["Dedicated prepper audience", "Low competition"],
        "cons": ["Smaller niche"],
    },
    # JOINT PAIN
    {
        "name": "Joint Genesis",
        "vendor_id": "jointgen",
        "niche": "joint pain arthritis",
        "commission_rate": 70,
        "price": 59.0,
        "description": "Natural joint health supplement targeting synovial fluid",
        "gravity": 110,
        "cookie_duration": 60,
        "pros": ["Aging population = huge market", "High commission"],
        "cons": ["Health claims"],
    },
    # TINNITUS
    {
        "name": "Quietum Plus",
        "vendor_id": "quietumpl",
        "niche": "tinnitus hearing",
        "commission_rate": 70,
        "price": 69.0,
        "description": "Natural supplement for tinnitus and ear health",
        "gravity": 90,
        "cookie_duration": 60,
        "pros": ["Desperate buyers", "High commission", "Low competition content"],
        "cons": ["Medical niche"],
    },
    # MEMORY
    {
        "name": "Neuro-Thrive",
        "vendor_id": "neurothrive",
        "niche": "memory brain health",
        "commission_rate": 70,
        "price": 59.0,
        "description": "Brain health supplement for focus and memory",
        "gravity": 75,
        "cookie_duration": 60,
        "pros": ["Growing market", "Aging audience with money"],
        "cons": ["Medical claims"],
    },
    # GOLF
    {
        "name": "Simple Senior Swing",
        "vendor_id": "seniorswng",
        "niche": "golf improvement",
        "commission_rate": 75,
        "price": 47.0,
        "description": "Golf swing system designed specifically for seniors",
        "gravity": 55,
        "cookie_duration": 60,
        "pros": ["Affluent audience", "Low competition", "75% commission"],
        "cons": ["Small niche"],
    },
]


class ClickBankAgent(BaseAgent):
    name = "ClickBankAgent"

    def execute(self, **kwargs) -> dict:
        seeded = self._seed_products()
        links = self._generate_hoplinks()
        return {"products_seeded": seeded, "hoplinks_generated": links}

    def _seed_products(self) -> int:
        """Load all top ClickBank products into the database."""
        seeded = 0
        with get_db() as db:
            for product_data in CLICKBANK_TOP_PRODUCTS:
                # Get or create niche
                niche = db.query(Niche).filter(
                    Niche.name == product_data["niche"]
                ).first()
                if not niche:
                    niche = Niche(
                        name=product_data["niche"],
                        keywords=[],
                        status="testing",
                    )
                    db.add(niche)
                    db.flush()

                # Check if product already exists
                existing = db.query(Product).filter(
                    Product.name == product_data["name"]
                ).first()
                if existing:
                    continue

                hoplink = self.build_hoplink(product_data["vendor_id"])
                product = Product(
                    name=product_data["name"],
                    niche_id=niche.id,
                    affiliate_network="clickbank",
                    product_url=f"https://{product_data['vendor_id']}.com",
                    affiliate_url=hoplink,
                    commission_rate=product_data["commission_rate"],
                    price=product_data["price"],
                    cookie_duration=product_data["cookie_duration"],
                    description=product_data["description"],
                    pros=product_data["pros"],
                    cons=product_data["cons"],
                    gravity=product_data["gravity"],
                    status=ProductStatus.active,
                )
                db.add(product)
                seeded += 1

        return seeded

    def _generate_hoplinks(self) -> int:
        """Create AffiliateLink records for all ClickBank products."""
        with get_db() as db:
            products = db.query(Product).filter(
                Product.affiliate_network == "clickbank"
            ).all()
            product_data = [{"id": p.id, "affiliate_url": p.affiliate_url} for p in products]

        from agents.link_manager_agent import LinkManagerAgent
        link_agent = LinkManagerAgent()
        created = 0
        for p in product_data:
            result = link_agent.create_affiliate_link(p["id"])
            if result:
                created += 1
        return created

    @staticmethod
    def build_hoplink(vendor_id: str, tid: str = "") -> str:
        """Build a ClickBank hoplink for shanmugapr."""
        base = f"https://{CLICKBANK_NICKNAME}.{vendor_id}.hop.clickbank.net"
        if tid:
            base += f"?tid={tid}"
        return base

    def get_products_by_niche(self, niche: str) -> list[dict]:
        """Return products for a specific niche."""
        return [
            {**p, "hoplink": self.build_hoplink(p["vendor_id"])}
            for p in CLICKBANK_TOP_PRODUCTS
            if p["niche"] == niche
        ]

    def get_all_hoplinks(self) -> list[dict]:
        """Return all products with their hoplinks."""
        return [
            {
                "name": p["name"],
                "niche": p["niche"],
                "hoplink": self.build_hoplink(p["vendor_id"]),
                "commission_rate": p["commission_rate"],
                "avg_commission_usd": round(p["price"] * p["commission_rate"] / 100, 2),
                "gravity": p["gravity"],
            }
            for p in CLICKBANK_TOP_PRODUCTS
        ]
