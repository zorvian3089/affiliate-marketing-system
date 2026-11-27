"""
Draft review: nothing from SITE_MODE=getupsignal goes live until approved here.
The /review page is a public shell; all data and actions under /api/review need the admin key.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from agents.static_site_agent import StaticSiteAgent, _markdown
from agents.product_content_agent import ProductContentAgent
from database.database import get_db
from database.models import ContentPiece, ContentStatus, Niche
from config.settings import PRODUCT_NICHE

router = APIRouter(tags=["review"])


@router.get("/api/review/drafts")
def list_drafts():
    with get_db() as db:
        rows = (db.query(ContentPiece).join(Niche, ContentPiece.niche_id == Niche.id)
                .filter(Niche.name == PRODUCT_NICHE, ContentPiece.status == ContentStatus.draft)
                .order_by(ContentPiece.created_at.asc()).all())
        return [{"id": r.id, "title": r.title, "words": r.word_count, "html": _markdown(r.body or "")}
                for r in rows]


@router.post("/api/review/generate")
def generate_now():
    """Write one draft on demand and report the real error to the (authenticated) owner."""
    try:
        return ProductContentAgent().run()
    except Exception as e:
        return {"created": 0, "reason": f"{type(e).__name__}: {e}"[:600]}


def _set_status(content_id: int, status: ContentStatus):
    with get_db() as db:
        piece = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
        if not piece or piece.status != ContentStatus.draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        piece.status = status


@router.post("/api/review/{content_id}/approve")
def approve(content_id: int):
    _set_status(content_id, ContentStatus.scheduled)  # "scheduled" = approved
    return StaticSiteAgent().execute()


@router.post("/api/review/{content_id}/reject")
def reject(content_id: int):
    _set_status(content_id, ContentStatus.failed)
    return {"rejected": content_id}


@router.get("/review", response_class=HTMLResponse)
def review_page():
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Review drafts</title>
<style>body{font-family:system-ui;max-width:820px;margin:24px auto;padding:0 16px}
iframe{width:100%;height:420px;border:1px solid #ccc;border-radius:8px}
button{padding:10px 18px;margin:8px 8px 28px 0;border:0;border-radius:6px;cursor:pointer;color:#fff}
.ok{background:#0f766e}.no{background:#b91c1c}</style></head><body>
<h2>Drafts waiting for approval</h2>
<button class="ok" id="gen">Write a draft now</button><p id="msg"></p><div id="list">Loading…</div>
<script>
let key = '';
async function call(path, method) {
  if (!key) key = prompt('Admin key (ADMIN_API_KEY from Render):') || '';
  const r = await fetch(path, {method: method || 'GET', headers: {'X-Admin-Key': key}});
  if (r.status === 401) { key = ''; throw new Error('Wrong admin key. Reload to try again.'); }
  if (!r.ok) throw new Error('Request failed: ' + r.status);
  return r.json();
}
async function load() {
  const box = document.getElementById('list');
  try {
    const drafts = await call('/api/review/drafts');
    box.textContent = drafts.length ? '' : 'No drafts right now.';
    for (const d of drafts) {
      const h = document.createElement('h3'); h.textContent = d.title + ' (' + d.words + ' words)';
      const f = document.createElement('iframe'); f.setAttribute('sandbox', '');
      f.srcdoc = '<body style="font-family:system-ui;line-height:1.6">' + d.html + '</body>';
      box.append(h, f);
      for (const [label, act, cls] of [['Approve and publish', 'approve', 'ok'], ['Reject', 'reject', 'no']]) {
        const b = document.createElement('button'); b.textContent = label; b.className = cls;
        b.onclick = async () => { b.disabled = true;
          try { await call('/api/review/' + d.id + '/' + act, 'POST'); load(); }
          catch (e) { alert(e.message); b.disabled = false; } };
        box.append(b);
      }
    }
  } catch (e) { box.textContent = e.message; }
}
document.getElementById('gen').onclick = async (ev) => {
  const b = ev.target, m = document.getElementById('msg');
  b.disabled = true; m.textContent = 'Writing… this can take a few minutes. Keep this page open.';
  try { const r = await call('/api/review/generate', 'POST');
    m.textContent = r.created ? 'Draft written: ' + r.title : 'No draft: ' + r.reason; load(); }
  catch (e) { m.textContent = e.message; }
  b.disabled = false;
};
load();
</script></body></html>"""
