"""
Orchestrator
The master scheduler that runs all agents on their schedules.
Handles failures, retries, and dependency ordering.
"""
import time
import logging
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from agents.niche_research_agent import NicheResearchAgent
from agents.product_discovery_agent import ProductDiscoveryAgent
from agents.content_creation_agent import ContentCreationAgent
from agents.seo_agent import SEOAgent
from agents.social_media_agent import SocialMediaAgent
from agents.email_agent import EmailAgent
from agents.link_manager_agent import LinkManagerAgent
from agents.analytics_agent import AnalyticsAgent
from agents.ab_testing_agent import ABTestingAgent
from agents.clickbank_agent import ClickBankAgent
from agents.customer_acquisition_agent import CustomerAcquisitionAgent
from agents.blogger_agent import BloggerAgent
from agents.wordpress_agent import WordPressAgent
from agents.bluesky_agent import BlueskyAgent
from database.database import init_db
from config.settings import (
    CONTENT_CREATION_INTERVAL, SOCIAL_POST_INTERVAL, EMAIL_CAMPAIGN_INTERVAL,
    ANALYTICS_INTERVAL, PRODUCT_DISCOVERY_INTERVAL, NICHE_RESEARCH_INTERVAL,
    SEO_AUDIT_INTERVAL, LINK_CHECK_INTERVAL
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """Master controller for all affiliate marketing agents."""

    def __init__(self):
        executors = {"default": ThreadPoolExecutor(4)}
        self.scheduler = BackgroundScheduler(
            executors=executors,
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
        )
        self._lock = threading.Lock()

    def start(self):
        init_db()
        logger.info("Database initialized")

        self._register_jobs()
        self.scheduler.start()
        logger.info("Orchestrator started — all agents scheduled")

        # Run bootstrap in background so server starts immediately
        t = threading.Thread(target=self._run_initial_cycle, daemon=True)
        t.start()

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("Orchestrator stopped")

    def _register_jobs(self):
        jobs = [
            ("niche_research", self._job_niche_research, NICHE_RESEARCH_INTERVAL),
            ("product_discovery", self._job_product_discovery, PRODUCT_DISCOVERY_INTERVAL),
            ("content_creation", self._job_content_creation, CONTENT_CREATION_INTERVAL),
            ("blogger_publish", self._job_blogger, 86400),  # once per day — safe pace
            ("wordpress_publish", self._job_wordpress, 86400),  # once per day
            ("bluesky_post", self._job_bluesky, 86400),         # once per day
            ("seo_audit", self._job_seo, SEO_AUDIT_INTERVAL),
            ("social_media", self._job_social_media, SOCIAL_POST_INTERVAL),
            ("email_sequences", self._job_email, EMAIL_CAMPAIGN_INTERVAL),
            ("link_check", self._job_link_manager, LINK_CHECK_INTERVAL),
            ("analytics", self._job_analytics, ANALYTICS_INTERVAL),
        ]

        for job_id, func, interval_seconds in jobs:
            self.scheduler.add_job(
                func,
                "interval",
                seconds=interval_seconds,
                id=job_id,
                replace_existing=True,
            )
            logger.info(f"  Registered job: {job_id} (every {interval_seconds//3600}h {(interval_seconds%3600)//60}m)")

    def _run_initial_cycle(self):
        """Run priority agents on startup to bootstrap the system."""
        logger.info("Running initial bootstrap cycle...")
        initial_jobs = [
            ("ClickBank Setup", self._job_clickbank),
            ("Analytics Snapshot", self._job_analytics),
            ("Link Manager", self._job_link_manager),
            ("Customer Acquisition", self._job_customer_acquisition),
        ]
        for name, job in initial_jobs:
            try:
                logger.info(f"  Bootstrap: {name}")
                job()
            except Exception as e:
                logger.error(f"  Bootstrap failed for {name}: {e}")

    # ── Job wrappers ───────────────────────────────────────────────────────────

    def _job_niche_research(self):
        self._safe_run("NicheResearch", lambda: NicheResearchAgent().run())

    def _job_product_discovery(self):
        self._safe_run("ProductDiscovery", lambda: ProductDiscoveryAgent().run())

    def _job_content_creation(self):
        self._safe_run("ContentCreation", lambda: ContentCreationAgent().run())

    def _job_seo(self):
        self._safe_run("SEO", lambda: SEOAgent().run())

    def _job_social_media(self):
        self._safe_run("SocialMedia", lambda: SocialMediaAgent().run())

    def _job_email(self):
        self._safe_run("Email", lambda: EmailAgent().run())

    def _job_link_manager(self):
        self._safe_run("LinkManager", lambda: LinkManagerAgent().run())

    def _job_analytics(self):
        self._safe_run("Analytics", lambda: AnalyticsAgent().run())

    def _job_clickbank(self):
        self._safe_run("ClickBank", lambda: ClickBankAgent().run())

    def _job_customer_acquisition(self):
        self._safe_run("CustomerAcquisition", lambda: CustomerAcquisitionAgent().run())

    def _job_blogger(self):
        self._safe_run("Blogger", lambda: BloggerAgent().run())

    def _job_wordpress(self):
        self._safe_run("WordPress", lambda: WordPressAgent().run())

    def _job_bluesky(self):
        self._safe_run("Bluesky", lambda: BlueskyAgent().run())

    def _safe_run(self, name: str, fn):
        with self._lock:
            try:
                logger.info(f"[Orchestrator] Starting {name} agent")
                result = fn()
                logger.info(f"[Orchestrator] {name} completed: {result}")
                return result
            except Exception as e:
                logger.error(f"[Orchestrator] {name} failed: {e}", exc_info=True)

    # ── Manual triggers ────────────────────────────────────────────────────────

    def run_agent_now(self, agent_name: str) -> dict:
        """Manually trigger any agent by name."""
        agents = {
            "niche": self._job_niche_research,
            "product": self._job_product_discovery,
            "content": self._job_content_creation,
            "seo": self._job_seo,
            "social": self._job_social_media,
            "email": self._job_email,
            "links": self._job_link_manager,
            "analytics": self._job_analytics,
            "clickbank": self._job_clickbank,
            "acquisition": self._job_customer_acquisition,
            "blogger": self._job_blogger,
            "wordpress": self._job_wordpress,
            "bluesky": self._job_bluesky,
        }
        job = agents.get(agent_name.lower())
        if not job:
            return {"error": f"Unknown agent: {agent_name}. Valid: {list(agents.keys())}"}

        t = threading.Thread(target=job, daemon=True)
        t.start()
        return {"status": "started", "agent": agent_name}

    def get_job_status(self) -> list[dict]:
        """Return status of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "status": "scheduled",
            })
        return jobs


# Singleton instance
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
