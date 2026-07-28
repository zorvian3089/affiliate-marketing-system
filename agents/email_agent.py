"""
Email Marketing Agent
Manages subscriber sequences, broadcasts, and automated campaigns.
Email is the highest-converting traffic source for affiliates.
"""
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import EmailSubscriber, EmailCampaign, EmailStatus, Product
from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    FROM_EMAIL, FROM_NAME
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert email copywriter for affiliate marketing.
You write emails that:
- Get opened (compelling subject lines)
- Get read (engaging storytelling, not salesy)
- Get clicked (natural CTAs that feel helpful)
- Build long-term trust with subscribers
- Have personal, conversational tone (not corporate)
- Use proven copywriting frameworks: AIDA, PAS, Story-bridge

Always respond with valid JSON only."""


class EmailAgent(BaseAgent):
    name = "EmailAgent"

    def execute(self, **kwargs) -> dict:
        sequence_sent = self._run_email_sequences()
        return {"sequence_emails_sent": sequence_sent}

    def create_welcome_sequence(self, niche: str, product_name: str, product_url: str) -> list[dict]:
        """Generate a 7-email welcome sequence for new subscribers."""
        prompt = f"""Create a 7-email welcome sequence for affiliate marketing in the "{niche}" niche.
Main product to promote: {product_name} ({product_url})

Email progression:
1. Welcome + instant value (day 0)
2. Your story / why you care about this niche (day 1)
3. Educational content — solve a problem (day 2)
4. Social proof + case study (day 3)
5. Soft product introduction (day 4)
6. Direct product recommendation with benefits (day 5)
7. Urgency/scarcity + final CTA (day 7)

Return JSON array (7 items):
[
  {{
    "sequence_step": 1,
    "delay_days": 0,
    "subject": "email subject line",
    "preview_text": "preview text shown in inbox (35-90 chars)",
    "body_html": "full HTML email body with {{first_name}} personalization",
    "body_text": "plain text version",
    "cta_text": "call to action button text",
    "cta_url": "{product_url}"
  }}
]"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=8000)
        except Exception as e:
            logger.error(f"Welcome sequence creation failed: {e}")
            return []

    def save_sequence(self, emails: list[dict], niche: str, campaign_name: str):
        with get_db() as db:
            for email in emails:
                campaign = EmailCampaign(
                    name=campaign_name,
                    campaign_type="sequence",
                    subject=email.get("subject", ""),
                    body_html=email.get("body_html", ""),
                    body_text=email.get("body_text", ""),
                    niche=niche,
                    sequence_step=email.get("sequence_step", 1),
                    status=EmailStatus.active,
                )
                db.add(campaign)

    def create_broadcast(self, niche: str, topic: str, product: dict | None = None) -> dict:
        """Create a one-time broadcast email."""
        product_info = ""
        if product:
            product_info = f"\nProduct to mention: {product['name']} — {product.get('description', '')}"

        prompt = f"""Write a broadcast email for {niche} subscribers about: "{topic}"
{product_info}

Return JSON:
{{
  "subject": "subject line (test A version)",
  "subject_b": "subject line (test B version — different angle)",
  "preview_text": "preview text",
  "body_html": "full HTML email",
  "body_text": "plain text version",
  "cta_text": "button text if applicable",
  "send_time_recommendation": "Tuesday 10am|Thursday 2pm|etc"
}}

Make the email feel personal, not like a mass blast. Lead with value, end with the offer."""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=4000)
        except Exception as e:
            logger.error(f"Broadcast creation failed: {e}")
            return {}

    def _run_email_sequences(self) -> int:
        """Send sequence emails to subscribers based on their step."""
        with get_db() as db:
            subscribers = db.query(EmailSubscriber).filter(
                EmailSubscriber.is_active == True
            ).all()

            sent_count = 0
            for subscriber in subscribers:
                next_step = subscriber.sequence_step + 1
                campaign = db.query(EmailCampaign).filter(
                    EmailCampaign.campaign_type == "sequence",
                    EmailCampaign.status == EmailStatus.active,
                    EmailCampaign.niche == subscriber.niche,
                    EmailCampaign.sequence_step == next_step,
                ).first()

                if campaign:
                    success = self._send_email(
                        to_email=subscriber.email,
                        to_name=subscriber.first_name or "Friend",
                        subject=campaign.subject,
                        body_html=campaign.body_html,
                        body_text=campaign.body_text,
                    )
                    if success:
                        subscriber.sequence_step = next_step
                        campaign.sent_count = (campaign.sent_count or 0) + 1
                        sent_count += 1

        return sent_count

    def send_broadcast_to_list(self, campaign_id: int, niche: str | None = None) -> dict:
        with get_db() as db:
            campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if not campaign:
                return {"error": "Campaign not found"}

            query = db.query(EmailSubscriber).filter(EmailSubscriber.is_active == True)
            if niche:
                query = query.filter(EmailSubscriber.niche == niche)
            subscribers = query.all()

            sent = 0
            failed = 0
            for sub in subscribers:
                body_html = (campaign.body_html or "").replace("{{first_name}}", sub.first_name or "Friend")
                success = self._send_email(
                    to_email=sub.email,
                    to_name=sub.first_name or "Friend",
                    subject=campaign.subject,
                    body_html=body_html,
                    body_text=campaign.body_text,
                )
                if success:
                    sent += 1
                else:
                    failed += 1

            campaign.sent_count = (campaign.sent_count or 0) + sent
            campaign.sent_at = datetime.utcnow()

        return {"sent": sent, "failed": failed, "total": sent + failed}

    def _send_email(self, to_email: str, to_name: str, subject: str,
                    body_html: str, body_text: str) -> bool:
        if not all([SMTP_USER, SMTP_PASSWORD, FROM_EMAIL]):
            logger.info(f"Email SMTP not configured — would send to {to_email}: {subject}")
            return True  # Simulate success when not configured

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
            msg["To"] = f"{to_name} <{to_email}>"

            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, to_email, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Email send failed to {to_email}: {e}")
            return False

    def add_subscriber(self, email: str, first_name: str, niche: str, source: str = "organic"):
        with get_db() as db:
            existing = db.query(EmailSubscriber).filter(EmailSubscriber.email == email).first()
            if not existing:
                sub = EmailSubscriber(
                    email=email,
                    first_name=first_name,
                    niche=niche,
                    source=source,
                    sequence_step=0,
                    is_active=True,
                )
                db.add(sub)
                return True
            return False

    def generate_subject_lines(self, topic: str, count: int = 10) -> list[str]:
        """A/B test subject line generator."""
        prompt = f"""Generate {count} email subject lines for topic: "{topic}"

Use different frameworks:
- Curiosity gap ("The one thing that...")
- Numbered lists ("7 ways to...")
- Question ("Are you making this mistake?")
- How-to ("How I made $X with...")
- Urgency ("Ending tonight: ...")
- Personalization + benefit

Return JSON array of {count} strings: ["subject1", "subject2", ...]"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt, max_tokens=1000)
        except Exception as e:
            logger.error(f"Subject line generation failed: {e}")
            return []
