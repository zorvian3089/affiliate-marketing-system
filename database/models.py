from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class NicheStatus(enum.Enum):
    active = "active"
    paused = "paused"
    testing = "testing"


class ProductStatus(enum.Enum):
    active = "active"
    inactive = "inactive"
    testing = "testing"


class ContentStatus(enum.Enum):
    draft = "draft"
    published = "published"
    scheduled = "scheduled"
    failed = "failed"


class EmailStatus(enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"


class Niche(Base):
    __tablename__ = "niches"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    keywords = Column(JSON)                  # list of target keywords
    competition_score = Column(Float)        # 0-100, lower = less competition
    monthly_searches = Column(Integer)
    avg_commission_rate = Column(Float)      # average % commission in niche
    status = Column(SAEnum(NicheStatus), default=NicheStatus.testing)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", back_populates="niche")
    content_pieces = relationship("ContentPiece", back_populates="niche")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    niche_id = Column(Integer, ForeignKey("niches.id"))
    affiliate_network = Column(String(50))   # amazon, clickbank, shareasale, etc.
    product_url = Column(String(500))
    affiliate_url = Column(String(500))
    commission_rate = Column(Float)          # percentage
    commission_fixed = Column(Float)         # fixed dollar amount
    price = Column(Float)
    cookie_duration = Column(Integer)        # days
    description = Column(Text)
    pros = Column(JSON)
    cons = Column(JSON)
    rating = Column(Float)
    status = Column(SAEnum(ProductStatus), default=ProductStatus.testing)
    gravity = Column(Float)                  # ClickBank gravity or equivalent
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    niche = relationship("Niche", back_populates="products")
    content_pieces = relationship("ContentPiece", secondary="content_products", back_populates="products")
    link_clicks = relationship("LinkClick", back_populates="product")
    conversions = relationship("Conversion", back_populates="product")


class AffiliateLink(Base):
    __tablename__ = "affiliate_links"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    short_code = Column(String(20), unique=True, nullable=False)
    original_url = Column(String(1000), nullable=False)
    cloaked_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    total_clicks = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    clicks = relationship("LinkClick", back_populates="link")


class LinkClick(Base):
    __tablename__ = "link_clicks"

    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("affiliate_links.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    referrer = Column(String(500))
    source = Column(String(100))             # email, social, organic, etc.
    clicked_at = Column(DateTime, default=datetime.utcnow)

    link = relationship("AffiliateLink", back_populates="clicks")
    product = relationship("Product", back_populates="link_clicks")


class Conversion(Base):
    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    commission_earned = Column(Float)
    sale_amount = Column(Float)
    source = Column(String(100))
    converted_at = Column(DateTime, default=datetime.utcnow)
    network_transaction_id = Column(String(200))

    product = relationship("Product", back_populates="conversions")


class ContentPiece(Base):
    __tablename__ = "content_pieces"

    id = Column(Integer, primary_key=True)
    niche_id = Column(Integer, ForeignKey("niches.id"))
    title = Column(String(300), nullable=False)
    slug = Column(String(300), unique=True)
    content_type = Column(String(50))        # blog_post, review, comparison, listicle
    body = Column(Text)
    meta_description = Column(String(160))
    target_keyword = Column(String(200))
    secondary_keywords = Column(JSON)
    word_count = Column(Integer)
    status = Column(SAEnum(ContentStatus), default=ContentStatus.draft)
    published_url = Column(String(500))
    seo_score = Column(Float)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime)

    niche = relationship("Niche", back_populates="content_pieces")
    products = relationship("Product", secondary="content_products", back_populates="content_pieces")
    social_posts = relationship("SocialPost", back_populates="content")


content_products = type("content_products", (Base,), {
    "__tablename__": "content_products",
    "__table_args__": {"extend_existing": True},
    "content_id": Column(Integer, ForeignKey("content_pieces.id"), primary_key=True),
    "product_id": Column(Integer, ForeignKey("products.id"), primary_key=True),
})


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey("content_pieces.id"), nullable=True)
    platform = Column(String(50))            # twitter, reddit, pinterest
    post_text = Column(Text)
    hashtags = Column(JSON)
    scheduled_at = Column(DateTime)
    posted_at = Column(DateTime)
    platform_post_id = Column(String(200))
    status = Column(String(20), default="scheduled")
    engagement = Column(JSON)               # likes, retweets, comments
    created_at = Column(DateTime, default=datetime.utcnow)

    content = relationship("ContentPiece", back_populates="social_posts")


class EmailSubscriber(Base):
    __tablename__ = "email_subscribers"

    id = Column(Integer, primary_key=True)
    email = Column(String(200), unique=True, nullable=False)
    first_name = Column(String(100))
    niche = Column(String(100))
    source = Column(String(100))             # organic, social, paid
    is_active = Column(Boolean, default=True)
    sequence_step = Column(Integer, default=0)
    tags = Column(JSON)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    unsubscribed_at = Column(DateTime)


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    campaign_type = Column(String(50))       # sequence, broadcast, welcome
    subject = Column(String(300))
    body_html = Column(Text)
    body_text = Column(Text)
    niche = Column(String(100))
    sequence_step = Column(Integer)
    status = Column(SAEnum(EmailStatus), default=EmailStatus.draft)
    sent_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    conversion_count = Column(Integer, default=0)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True)
    agent_name = Column(String(100), nullable=False)
    task = Column(String(500))
    status = Column(String(20))             # success, failed, running
    result_summary = Column(Text)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class RevenueSnapshot(Base):
    __tablename__ = "revenue_snapshots"

    id = Column(Integer, primary_key=True)
    date = Column(String(10), unique=True)  # YYYY-MM-DD
    total_clicks = Column(Integer, default=0)
    total_conversions = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    revenue_by_network = Column(JSON)
    revenue_by_niche = Column(JSON)
    revenue_by_product = Column(JSON)
    top_content = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
