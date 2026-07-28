from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.database import get_db_session
from database.models import ContentPiece, ContentStatus
from datetime import datetime

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/")
def list_content(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db_session)
):
    query = db.query(ContentPiece)
    if status:
        query = query.filter(ContentPiece.status == status)
    total = query.count()
    items = query.order_by(ContentPiece.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "slug": c.slug,
                "content_type": c.content_type,
                "status": c.status.value if c.status else None,
                "target_keyword": c.target_keyword,
                "word_count": c.word_count,
                "seo_score": c.seo_score,
                "views": c.views,
                "published_url": c.published_url,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in items
        ],
    }


@router.get("/{content_id}")
def get_content(content_id: int, db: Session = Depends(get_db_session)):
    content = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return {
        "id": content.id,
        "title": content.title,
        "slug": content.slug,
        "body": content.body,
        "meta_description": content.meta_description,
        "target_keyword": content.target_keyword,
        "secondary_keywords": content.secondary_keywords,
        "status": content.status.value if content.status else None,
        "word_count": content.word_count,
        "seo_score": content.seo_score,
        "views": content.views,
        "published_url": content.published_url,
    }


class PublishRequest(BaseModel):
    published_url: str


@router.post("/{content_id}/publish")
def publish_content(content_id: int, req: PublishRequest, db: Session = Depends(get_db_session)):
    content = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    content.status = ContentStatus.published
    content.published_url = req.published_url
    content.published_at = datetime.utcnow()
    db.commit()
    return {"status": "published", "url": req.published_url}


@router.delete("/{content_id}")
def delete_content(content_id: int, db: Session = Depends(get_db_session)):
    content = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    db.delete(content)
    db.commit()
    return {"deleted": True}
