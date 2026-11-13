from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from ..models import City, Feedback, MediaItem, Village, VillageSection
from ..schemas import FeedbackCreate
from ..services.feedback_mail import send_feedback_notification
from ..services.serializers import city_payload, feedback_payload, village_detail, village_summary

router = APIRouter(prefix='/api', tags=['public'])

_COOLDOWN_SECONDS = 60
_WINDOW_SECONDS = 3600
_MAX_PER_WINDOW = 5
_feedback_buckets: dict[str, deque[float]] = defaultdict(deque)
_feedback_lock = Lock()


def _allow_feedback_request(key: str) -> bool:
    now = monotonic()
    with _feedback_lock:
        bucket = _feedback_buckets[key]
        while bucket and now - bucket[0] >= _WINDOW_SECONDS:
            bucket.popleft()
        if bucket and now - bucket[-1] < _COOLDOWN_SECONDS:
            return False
        if len(bucket) >= _MAX_PER_WINDOW:
            return False
        bucket.append(now)
        return True


def village_options():
    return (
        selectinload(Village.city), selectinload(Village.sections), selectinload(Village.figures),
        selectinload(Village.historic_elements), selectinload(Village.media),
    )

@router.get('/health')
def health():
    return {'status': 'ok'}

@router.get('/stats')
def public_stats(db: Session = Depends(get_db)):
    published = Village.status == 'published'
    village_count = db.scalar(select(func.count(Village.id)).where(published)) or 0
    city_count = db.scalar(select(func.count(func.distinct(Village.city_id))).where(published)) or 0
    section_count = db.scalar(select(func.count(VillageSection.id)).join(Village).where(published)) or 0
    heritage_count = db.scalar(select(func.count(VillageSection.id)).join(Village).where(published, VillageSection.type == 'intangible_heritage')) or 0
    image_count = db.scalar(select(func.count(MediaItem.id)).join(Village).where(published, MediaItem.media_type == 'image')) or 0
    return {
        'village_count': village_count, 'city_count': city_count, 'section_count': section_count,
        'intangible_heritage_count': heritage_count, 'image_count': image_count,
    }

@router.get('/cities')
def list_cities(db: Session = Depends(get_db)):
    rows = db.execute(
        select(City, func.count(Village.id)).outerjoin(
            Village, and_(Village.city_id == City.id, Village.status == 'published')
        ).group_by(City.id).order_by(City.sort_order, City.id)
    ).all()
    return [city_payload(city, count) for city, count in rows]

@router.get('/cities/{slug}/villages')
def city_villages(slug: str, db: Session = Depends(get_db)):
    city = db.scalar(select(City).where(City.slug == slug))
    if not city:
        raise HTTPException(status_code=404, detail='城市不存在')
    villages = db.scalars(
        select(Village).where(Village.city_id == city.id, Village.status == 'published').options(selectinload(Village.city), selectinload(Village.media)).order_by(Village.sort_order, Village.id)
    ).all()
    items = []
    for village in villages:
        item = village_summary(village)
        item.pop('summary', None)
        items.append(item)
    return {'city': city_payload(city, len(items)), 'villages': items}

@router.get('/villages')
def list_villages(q: str = '', city: str = '', limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    stmt = select(Village).where(Village.status == 'published').options(selectinload(Village.city), selectinload(Village.media))
    if q:
        stmt = stmt.where(or_(Village.name.contains(q), Village.location.contains(q), Village.summary.contains(q)))
    if city:
        stmt = stmt.join(City).where(or_(City.slug == city, City.name == city))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    villages = db.scalars(stmt.order_by(Village.sort_order, Village.id).offset(offset).limit(limit)).all()
    return {'total': total, 'items': [village_summary(x) for x in villages]}

@router.get('/villages/{village_ref}')
def get_village(village_ref: str, db: Session = Depends(get_db)):
    conditions = [Village.slug == village_ref, Village.source_id == village_ref]
    if village_ref.isdigit():
        conditions.append(Village.id == int(village_ref))
    village = db.scalar(select(Village).where(Village.status == 'published', or_(*conditions)).options(*village_options()))
    if not village:
        raise HTTPException(status_code=404, detail='村落不存在或尚未发布')
    return village_detail(village)

@router.post('/feedback', status_code=201)
def create_feedback(payload: FeedbackCreate, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    generic = {'status': 'ok', 'message': '反馈已提交'}
    if payload.website:
        return generic
    client_ip = request.client.host if request.client else 'unknown'
    if not _allow_feedback_request(client_ip):
        raise HTTPException(status_code=429, detail='提交过于频繁，请稍后再试。')
    data = payload.model_dump(exclude={'website'})
    recent_start = datetime.now(timezone.utc) - timedelta(minutes=10)
    duplicate = db.scalar(
        select(Feedback.id).where(
            Feedback.message == data['message'],
            Feedback.village_name == data['village_name'],
            Feedback.created_at >= recent_start,
        ).limit(1)
    )
    if duplicate:
        return generic
    item = Feedback(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    background_tasks.add_task(send_feedback_notification, item)
    return {**generic, 'id': item.id}
