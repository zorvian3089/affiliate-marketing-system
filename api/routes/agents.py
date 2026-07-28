from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.orchestrator import get_orchestrator
from agents.niche_research_agent import NicheResearchAgent
from agents.content_creation_agent import ContentCreationAgent
from agents.email_agent import EmailAgent
from agents.analytics_agent import AnalyticsAgent
from agents.clickbank_agent import ClickBankAgent
from agents.customer_acquisition_agent import CustomerAcquisitionAgent

router = APIRouter(prefix="/api/agents", tags=["agents"])


class RunAgentRequest(BaseModel):
    agent: str


class CreateContentRequest(BaseModel):
    niche_id: int | None = None
    max_articles: int = 3


class CreateSequenceRequest(BaseModel):
    niche: str
    product_name: str
    product_url: str
    campaign_name: str


class AddSubscriberRequest(BaseModel):
    email: str
    first_name: str
    niche: str
    source: str = "manual"


@router.post("/run")
def run_agent(req: RunAgentRequest):
    """Manually trigger an agent."""
    orchestrator = get_orchestrator()
    result = orchestrator.run_agent_now(req.agent)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/status")
def get_agent_status():
    """Get all agent schedules."""
    orchestrator = get_orchestrator()
    return orchestrator.get_job_status()


@router.post("/content/create")
def create_content(req: CreateContentRequest):
    """Trigger content creation."""
    agent = ContentCreationAgent()
    result = agent.run(niche_id=req.niche_id, max_articles=req.max_articles)
    return result


@router.post("/research/niches")
def research_niches(niches: list[str] | None = None):
    """Run niche research."""
    agent = NicheResearchAgent()
    result = agent.run(niches=niches)
    return result


@router.post("/email/sequence")
def create_email_sequence(req: CreateSequenceRequest):
    """Create a new email welcome sequence."""
    agent = EmailAgent()
    emails = agent.create_welcome_sequence(req.niche, req.product_name, req.product_url)
    if emails:
        agent.save_sequence(emails, req.niche, req.campaign_name)
        return {"status": "created", "emails": len(emails)}
    raise HTTPException(status_code=500, detail="Failed to create sequence")


@router.post("/email/subscribers")
def add_subscriber(req: AddSubscriberRequest):
    """Add a new email subscriber."""
    agent = EmailAgent()
    added = agent.add_subscriber(req.email, req.first_name, req.niche, req.source)
    return {"added": added, "email": req.email}


@router.get("/analytics/summary")
def get_analytics(days: int = 30):
    agent = AnalyticsAgent()
    return agent.get_revenue_summary(days=days)


@router.get("/clickbank/hoplinks")
def get_all_hoplinks():
    """Return all your ClickBank affiliate links with shanmugapr nickname."""
    agent = ClickBankAgent()
    return agent.get_all_hoplinks()


@router.post("/clickbank/setup")
def setup_clickbank():
    """Seed all ClickBank products into the database."""
    agent = ClickBankAgent()
    result = agent.run()
    return result


@router.post("/acquisition/run")
def run_acquisition(niche: str | None = None):
    """Run customer acquisition agent for all or specific niche."""
    agent = CustomerAcquisitionAgent()
    if niche:
        return agent.generate_content_for_niche(niche)
    return agent.run()
