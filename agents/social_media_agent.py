"""
Social Media Agent
Creates and schedules posts for Twitter/X, Reddit, Pinterest.
Drives free traffic to affiliate content.
"""
import logging
import time
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost
from config.settings import (
    TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD,
    BASE_URL
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a social media expert for affiliate marketing.
You create posts that:
- Drive traffic without being spammy
- Provide genuine value to the audience
- Naturally lead people to click through to full content
- Use platform-appropriate tone and format
- Include strategic hashtags

Always respond with valid JSON only."""


class SocialMediaAgent(BaseAgent):
    name = "SocialMediaAgent"

    def execute(self, **kwargs) -> dict:
        # Get recent published content to promote
        with get_db() as db:
            recent_content = db.query(ContentPiece).filter(
                ContentPiece.status == "published",
                ContentPiece.published_url.isnot(None)
            ).order_by(ContentPiece.published_at.desc()).limit(5).all()
            content_data = [
                {"id": c.id, "title": c.title, "slug": c.slug,
                 "meta_description": c.meta_description, "target_keyword": c.target_keyword}
                for c in recent_content
            ]

        if not content_data:
            # Even without published content, create value posts
            content_data = [{"id": None, "title": "affiliate tips", "slug": "",
                             "meta_description": "", "target_keyword": "affiliate marketing"}]

        posts_created = 0
        for content in content_data[:3]:
            # Create posts for each platform
            for platform in ["twitter", "reddit"]:
                post = self._create_post(content, platform)
                if post:
                    self._schedule_post(post, content["id"])
                    posts_created += 1

        sent = self._send_scheduled_posts()
        return {"posts_created": posts_created, "posts_sent": sent}

    def _create_post(self, content: dict, platform: str) -> dict | None:
        url = f"{BASE_URL}/go/{content['slug']}" if content.get("slug") else BASE_URL

        platform_guides = {
            "twitter": """Twitter/X post requirements:
- Max 280 characters (leave 23 for URL)
- Hook in first line (question, stat, or bold claim)
- 2-3 relevant hashtags
- Strong CTA""",
            "reddit": """Reddit post requirements:
- Helpful, non-spammy title
- Provide genuine value in post body
- Only link if it naturally fits
- Match subreddit tone
- No obvious self-promotion""",
            "pinterest": """Pinterest pin requirements:
- Descriptive, keyword-rich title
- Detailed description with keywords
- Vertical image recommended
- Clear value proposition""",
        }

        prompt = f"""Create a {platform} post to promote this affiliate content:

Title: {content['title']}
Description: {content.get('meta_description', '')}
URL: {url}
Target keyword: {content.get('target_keyword', '')}

{platform_guides.get(platform, '')}

Return JSON:
{{
  "platform": "{platform}",
  "post_text": "the actual post text",
  "hashtags": ["tag1", "tag2"],
  "subreddit": "relevant_subreddit_name" (only for reddit),
  "character_count": <integer>,
  "best_time_to_post": "morning|afternoon|evening",
  "engagement_tip": "one tip to boost engagement on this specific post"
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Post creation failed for {platform}: {e}")
            return None

    def _schedule_post(self, post_data: dict, content_id: int | None):
        # Schedule for next optimal time slot
        now = datetime.utcnow()
        best_time = post_data.get("best_time_to_post", "morning")
        delay_hours = {"morning": 2, "afternoon": 6, "evening": 10}.get(best_time, 4)
        scheduled = now + timedelta(hours=delay_hours)

        with get_db() as db:
            social_post = SocialPost(
                content_id=content_id,
                platform=post_data.get("platform", "unknown"),
                post_text=post_data.get("post_text", ""),
                hashtags=post_data.get("hashtags", []),
                scheduled_at=scheduled,
                status="scheduled",
            )
            db.add(social_post)

    def _send_scheduled_posts(self) -> int:
        with get_db() as db:
            due_posts = db.query(SocialPost).filter(
                SocialPost.status == "scheduled",
                SocialPost.scheduled_at <= datetime.utcnow()
            ).all()
            posts_data = [
                {"id": p.id, "platform": p.platform, "post_text": p.post_text, "hashtags": p.hashtags}
                for p in due_posts
            ]

        sent = 0
        for post in posts_data:
            success = self._send_post(post)
            if success:
                with get_db() as db:
                    p = db.query(SocialPost).filter(SocialPost.id == post["id"]).first()
                    if p:
                        p.status = "posted"
                        p.posted_at = datetime.utcnow()
                sent += 1
        return sent

    def _send_post(self, post: dict) -> bool:
        platform = post["platform"]

        if platform == "twitter":
            return self._post_to_twitter(post)
        elif platform == "reddit":
            return self._post_to_reddit(post)
        return False

    def _post_to_twitter(self, post: dict) -> bool:
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
            logger.info("Twitter credentials not configured — skipping post")
            return True  # Mark as handled to avoid loop

        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET,
            )
            text = post["post_text"]
            if post.get("hashtags"):
                hashtag_str = " ".join(f"#{h.lstrip('#')}" for h in post["hashtags"][:3])
                if len(text) + len(hashtag_str) + 1 <= 280:
                    text = f"{text} {hashtag_str}"
            client.create_tweet(text=text[:280])
            logger.info("Posted to Twitter successfully")
            return True
        except ImportError:
            logger.warning("tweepy not installed — install it to enable Twitter posting")
            return False
        except Exception as e:
            logger.error(f"Twitter post failed: {e}")
            return False

    def _post_to_reddit(self, post: dict) -> bool:
        if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD]):
            logger.info("Reddit credentials not configured — skipping post")
            return True

        try:
            import praw
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                username=REDDIT_USERNAME,
                password=REDDIT_PASSWORD,
                user_agent="AffiliateBot/1.0",
            )
            # Post as a self-post (text, not link) for better acceptance
            subreddit_name = "entrepreneur"  # default; ideally from post data
            subreddit = reddit.subreddit(subreddit_name)
            subreddit.submit(
                title=post["post_text"][:300],
                selftext=post["post_text"],
            )
            logger.info(f"Posted to Reddit r/{subreddit_name}")
            return True
        except ImportError:
            logger.warning("praw not installed — install it to enable Reddit posting")
            return False
        except Exception as e:
            logger.error(f"Reddit post failed: {e}")
            return False

    def generate_content_calendar(self, niche: str, days: int = 7) -> list[dict]:
        """Generate a social media content calendar."""
        prompt = f"""Create a {days}-day social media content calendar for affiliate marketing in the "{niche}" niche.

Mix of content types: educational tips, product highlights, personal stories, questions, stats.

Return JSON array ({days} items):
[
  {{
    "day": 1,
    "platform": "twitter|reddit",
    "content_type": "tip|highlight|question|story|stat",
    "post_text": "actual post text",
    "hashtags": ["tag1", "tag2"],
    "optimal_time": "9am|12pm|6pm"
  }}
]"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Content calendar generation failed: {e}")
            return []
