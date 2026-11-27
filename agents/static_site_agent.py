"""
Static Site Agent
Builds a fast, SEO-friendly first-party blog from the database and publishes drafts to it.

Output goes to site_output/ and is served by FastAPI at /blog (see api/main.py), so no
extra hosting is needed. The folder can also be pushed to Cloudflare Pages / GitHub Pages
and pointed at a custom domain later (set SITE_URL).

Every page carries: FTC affiliate disclosure, rel="sponsored nofollow" on affiliate links,
canonical URL, meta description, Article JSON-LD, sitemap.xml and an email signup form.
"""
import html
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, ContentStatus, Product, Niche, PUBLISHABLE_TYPES
from config.settings import BASE_DIR, BASE_URL, SITE_NAME, SITE_URL, ENABLE_STATIC_SITE, TARGET_NICHES

logger = logging.getLogger(__name__)

SITE_DIR = Path(BASE_DIR) / "site_output"
MAX_PUBLISH_PER_RUN = 3

_AFF_PLACEHOLDER_LINK = re.compile(r"\[([^\]]+)\]\(\s*\[?AFFILIATE_LINK\]?\s*\)")
_ANCHOR = re.compile(r'<a\s+([^>]*?)href="([^"]+)"([^>]*)>', re.I)

CSS = """
:root{--bg:#fff;--fg:#1f2937;--muted:#6b7280;--brand:#0f766e;--card:#f8fafc;--line:#e5e7eb}
@media(prefers-color-scheme:dark){:root{--bg:#0f172a;--fg:#e5e7eb;--muted:#94a3b8;--brand:#2dd4bf;--card:#1e293b;--line:#334155}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.7 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--brand)}header,footer,main{max-width:760px;margin:0 auto;padding:16px}
header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line)}
header a{text-decoration:none;font-weight:700}h1{line-height:1.25}h2{margin-top:2em}
.disclosure{background:var(--card);border-left:4px solid var(--brand);padding:10px 14px;font-size:14px;color:var(--muted);border-radius:4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0}
.card h2{margin:0 0 4px;font-size:20px}.meta{color:var(--muted);font-size:14px}
form.signup{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;margin:40px 0}
form.signup input[type=email]{width:100%;padding:12px;border:1px solid var(--line);border-radius:8px;font-size:16px;margin:8px 0}
form.signup button{background:var(--brand);color:#fff;border:0;padding:12px 20px;border-radius:8px;font-size:16px;cursor:pointer}
.hp{position:absolute;left:-9999px}table{border-collapse:collapse;width:100%}td,th{border:1px solid var(--line);padding:8px}
footer{color:var(--muted);font-size:14px;border-top:1px solid var(--line);margin-top:40px}
"""

DISCLOSURE = ('<p class="disclosure"><strong>Affiliate disclosure:</strong> some links on this page are affiliate '
              'links. If you buy through them we may earn a commission at no extra cost to you. This never '
              'changes our assessment. <a href="{u}/disclosure/">Learn more</a>.</p>')


def _signup_form(niche: str) -> str:
    return f"""<form class="signup" id="signup">
<strong>Get our best picks by email</strong>
<p class="meta">Occasional, useful buying guides. Unsubscribe any time.</p>
<input type="email" name="email" placeholder="you@example.com" required>
<input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
<button type="submit">Subscribe</button> <span id="signup-msg" class="meta"></span>
</form>
<script>
document.getElementById('signup').addEventListener('submit',async function(e){{
  e.preventDefault();var f=e.target,m=document.getElementById('signup-msg');
  try{{var r=await fetch({json.dumps(BASE_URL.rstrip('/') + '/api/subscribe')},{{method:'POST',
    headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:f.email.value,
    website:f.website.value,niche:{json.dumps(niche)}}})}});var d=await r.json();
    m.textContent=d.ok?'Thanks — you are subscribed!':(d.error||'Something went wrong.');if(d.ok)f.reset();}}
  catch(x){{m.textContent='Network error — please try again.';}}
}});
</script>"""


def _page(title: str, desc: str, canonical: str, body: str, extra_head: str = "") -> str:
    e = html.escape
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:type" content="article">
<style>{CSS}</style>{extra_head}</head><body>
<header><a href="{e(SITE_URL)}/">{e(SITE_NAME)}</a><a href="{e(SITE_URL)}/disclosure/">Disclosure</a></header>
<main>{body}</main>
<footer>&copy; {datetime.utcnow().year} {e(SITE_NAME)} · <a href="{e(SITE_URL)}/disclosure/">Affiliate disclosure</a>
<p>Content is for general information, not professional advice.</p></footer></body></html>"""


def _markdown(md_text: str) -> str:
    try:
        import markdown
        return markdown.markdown(md_text, extensions=["extra", "toc", "nl2br"])
    except ImportError:
        out = []
        for line in md_text.splitlines():
            if line.startswith("### "): out.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("## "): out.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("# "): out.append(f"<h2>{html.escape(line[2:])}</h2>")
            elif line.strip(): out.append(f"<p>{html.escape(line)}</p>")
        return "\n".join(out)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "article"


class StaticSiteAgent(BaseAgent):
    name = "StaticSiteAgent"

    def __init__(self):
        self.client = None
        self.model = None  # no LLM needed

    def execute(self, **kwargs) -> dict:
        if not ENABLE_STATIC_SITE:
            return {"skipped": True, "reason": "ENABLE_STATIC_SITE=false"}
        published = self._publish_drafts()
        built = self.build_site()
        return {"newly_published": published, "pages_built": built, "site_url": SITE_URL}

    # ── Publishing ─────────────────────────────────────────────────────────────

    def _publish_drafts(self) -> int:
        """Move drafts onto the site. One at a time per run keeps a natural cadence."""
        n = 0
        with get_db() as db:
            drafts = (
                db.query(ContentPiece)
                .join(Niche, ContentPiece.niche_id == Niche.id)
                .filter(
                    Niche.name.in_(TARGET_NICHES),  # off-focus (health) content never goes live
                    ContentPiece.status == ContentStatus.draft,
                    ContentPiece.published_url == None,  # noqa: E711
                    ContentPiece.content_type.in_(PUBLISHABLE_TYPES),
                    ContentPiece.body != None,  # noqa: E711
                )
                .order_by(ContentPiece.created_at.asc())
                .limit(MAX_PUBLISH_PER_RUN)
                .all()
            )
            for p in drafts:
                if len((p.body or "").split()) < 300:  # thin/failed generations don't go live
                    continue
                p.status = ContentStatus.published
                p.published_at = datetime.utcnow()
                p.published_url = f"{SITE_URL}/{self._path_for(p)}/"
                n += 1
        return n

    @staticmethod
    def _path_for(p) -> str:
        return f"articles/{_slugify(p.slug or p.title)}"

    # ── Build ──────────────────────────────────────────────────────────────────

    def build_site(self) -> int:
        with get_db() as db:
            pieces = (
                db.query(ContentPiece)
                .join(Niche, ContentPiece.niche_id == Niche.id)
                .filter(
                    Niche.name.in_(TARGET_NICHES),
                    ContentPiece.status == ContentStatus.published,
                    ContentPiece.published_url.like(f"{SITE_URL}/%"),
                )
                .order_by(ContentPiece.published_at.desc())
                .all()
            )
            products = [
                {"name": pr.name.lower(), "url": pr.affiliate_url or pr.product_url or ""}
                for pr in db.query(Product).all()
                if (pr.affiliate_url or "").startswith("http") and "/go/" not in (pr.affiliate_url or "")
            ]
            niche_names = {p.id: (p.niche.name if p.niche else "general") for p in pieces}
            items = [{
                "path": self._path_for(p), "title": p.title, "desc": p.meta_description or "",
                "body": p.body or "", "keyword": p.target_keyword or "",
                "date": (p.published_at or p.created_at or datetime.utcnow()),
                "niche": niche_names[p.id],
            } for p in pieces]

        shutil.rmtree(SITE_DIR / "articles", ignore_errors=True)  # drop pages no longer listed
        SITE_DIR.mkdir(parents=True, exist_ok=True)
        for it in items:
            self._write(f"{it['path']}/index.html", self._render_article(it, products))
        self._write("index.html", self._render_index(items))
        self._write("disclosure/index.html", self._render_disclosure())
        self._write("sitemap.xml", self._render_sitemap(items))
        self._write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
        logger.info(f"Static site built: {len(items)} articles → {SITE_DIR}")
        return len(items) + 4

    def _write(self, rel: str, content: str):
        path = SITE_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _resolve_link(self, it: dict, products: list[dict]) -> str | None:
        text = f"{it['title']} {it['keyword']}".lower()
        for pr in products:
            if pr["name"] and pr["name"] in text:
                return pr["url"]
        return None

    def _render_article(self, it: dict, products: list[dict]) -> str:
        e = html.escape
        body = it["body"]
        link = self._resolve_link(it, products)
        if link:
            body = body.replace("[AFFILIATE_LINK]", link)
        else:  # no verified link: drop the placeholder rather than ship a broken URL
            body = _AFF_PLACEHOLDER_LINK.sub(r"\1", body).replace("[AFFILIATE_LINK]", "")
        content = _markdown(body)

        def _rel(m):  # mark commercial links
            href = m.group(2)
            if href.startswith(SITE_URL) or href.startswith("/") or href.startswith("#"):
                return m.group(0)
            attrs = re.sub(r'\srel="[^"]*"', "", m.group(1) + m.group(3))
            return f'<a {attrs.strip()} href="{href}" rel="sponsored nofollow noopener" target="_blank">'
        content = _ANCHOR.sub(_rel, content)

        url = f"{SITE_URL}/{it['path']}/"
        ld = {"@context": "https://schema.org", "@type": "Article", "headline": it["title"],
              "description": it["desc"], "datePublished": it["date"].strftime("%Y-%m-%d"),
              "mainEntityOfPage": url}
        head = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
        body_html = (f"<article><h1>{e(it['title'])}</h1>"
                     f'<p class="meta">Updated {it["date"].strftime("%B %d, %Y")} · {e(it["niche"])}</p>'
                     f"{DISCLOSURE.format(u=SITE_URL)}{content}</article>{_signup_form(it['niche'])}")
        return _page(it["title"], it["desc"] or it["title"], url, body_html, head)

    def _render_index(self, items: list[dict]) -> str:
        e = html.escape
        cards = "".join(
            f'<div class="card"><h2><a href="{e(SITE_URL)}/{it["path"]}/">{e(it["title"])}</a></h2>'
            f'<div class="meta">{it["date"].strftime("%b %d, %Y")} · {e(it["niche"])}</div>'
            f'<p>{e(it["desc"])}</p></div>' for it in items
        ) or "<p>First guides are on the way — subscribe below.</p>"
        body = (f"<h1>{e(SITE_NAME)}</h1><p>Independent buying guides and reviews.</p>"
                f"{DISCLOSURE.format(u=SITE_URL)}{cards}{_signup_form('general')}")
        return _page(SITE_NAME, f"{SITE_NAME}: independent buying guides and reviews.", f"{SITE_URL}/", body)

    def _render_disclosure(self) -> str:
        body = (f"<h1>Affiliate disclosure</h1><p>{html.escape(SITE_NAME)} participates in affiliate programs. "
                "When you click a link marked as sponsored and make a purchase, we may earn a commission at no "
                "additional cost to you. Commissions do not change what we write: we describe vendor claims as "
                "claims, note where evidence is limited, and include drawbacks. We have not necessarily tested "
                "every product we cover. Nothing here is medical, legal or financial advice.</p>")
        return _page("Affiliate disclosure", "How we make money and how we review.", f"{SITE_URL}/disclosure/", body)

    def _render_sitemap(self, items: list[dict]) -> str:
        urls = [f"{SITE_URL}/", f"{SITE_URL}/disclosure/"] + [f"{SITE_URL}/{i['path']}/" for i in items]
        rows = "".join(f"<url><loc>{html.escape(u)}</loc></url>" for u in urls)
        return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'
