from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from ..config import MAX_UPLOAD_BYTES
from ..database import get_db
from ..dependencies import get_current_admin
from ..models import AdminUser, City, Feedback, HistoricElement, MediaItem, Village, VillageFigure, VillageSection
from ..schemas import (
    CityInput, FeedbackUpdate, FigureInput, HistoricElementInput, MediaInput, ReorderInput,
    SectionInput, VillageInput, VillageStatusInput,
)
from ..services.importer import import_processed
from ..services.media import ImageValidationError, delete_local_upload, save_uploaded_image
from ..services.serializers import city_payload, feedback_payload, village_detail, village_summary

router = APIRouter(prefix='/api/admin', tags=['admin'], dependencies=[Depends(get_current_admin)])

def village_options():
    return (
        selectinload(Village.city), selectinload(Village.sections), selectinload(Village.figures),
        selectinload(Village.historic_elements), selectinload(Village.media),
    )

def get_village(db: Session, village_id: int) -> Village:
    village = db.scalar(select(Village).where(Village.id == village_id).options(*village_options()))
    if not village:
        raise HTTPException(status_code=404, detail='村落不存在')
    return village

def get_section(db: Session, section_id: int) -> VillageSection:
    item = db.get(VillageSection, section_id)
    if not item:
        raise HTTPException(status_code=404, detail='内容模块不存在')
    return item

def get_figure(db: Session, figure_id: int) -> VillageFigure:
    item = db.get(VillageFigure, figure_id)
    if not item:
        raise HTTPException(status_code=404, detail='历史人物不存在')
    return item

def get_historic(db: Session, element_id: int) -> HistoricElement:
    item = db.get(HistoricElement, element_id)
    if not item:
        raise HTTPException(status_code=404, detail='历史环境要素不存在')
    return item

def get_media(db: Session, media_id: int) -> MediaItem:
    item = db.get(MediaItem, media_id)
    if not item:
        raise HTTPException(status_code=404, detail='媒体不存在')
    return item

def apply_village(v: Village, payload: VillageInput, db: Session):
    if payload.status not in ('draft', 'published'):
        raise HTTPException(status_code=422, detail='status 只能为 draft 或 published')
    if not db.get(City, payload.city_id):
        raise HTTPException(status_code=422, detail='城市不存在')
    for key, value in payload.model_dump().items():
        setattr(v, key, value)

@router.get('/stats')
def admin_stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Village.id))) or 0
    published = db.scalar(select(func.count(Village.id)).where(Village.status == 'published')) or 0
    draft = db.scalar(select(func.count(Village.id)).where(Village.status == 'draft')) or 0
    feedback_new = db.scalar(select(func.count(Feedback.id)).where(Feedback.status == 'new')) or 0
    return {'villages': total, 'published': published, 'draft': draft, 'new_feedback': feedback_new}

@router.get('/cities')
def admin_cities(db: Session = Depends(get_db)):
    rows = db.execute(select(City).order_by(City.sort_order, City.id)).scalars().all()
    counts = dict(db.execute(select(Village.city_id, func.count(Village.id)).group_by(Village.city_id)).all())
    return [city_payload(city, counts.get(city.id, 0)) for city in rows]

@router.post('/cities', status_code=201)
def create_city(payload: CityInput, db: Session = Depends(get_db)):
    city = City(**payload.model_dump())
    db.add(city)
    try:
        db.commit(); db.refresh(city)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='城市名称、slug 或行政区划代码已存在')
    return city_payload(city, 0)

@router.put('/cities/{city_id}')
def update_city(city_id: int, payload: CityInput, db: Session = Depends(get_db)):
    city = db.get(City, city_id)
    if not city:
        raise HTTPException(status_code=404, detail='城市不存在')
    for key, value in payload.model_dump().items():
        setattr(city, key, value)
    try:
        db.commit(); db.refresh(city)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='城市名称、slug 或行政区划代码已存在')
    counts = db.scalar(select(func.count(Village.id)).where(Village.city_id == city.id)) or 0
    return city_payload(city, counts)

@router.delete('/cities/{city_id}')
def delete_city(city_id: int, db: Session = Depends(get_db)):
    city = db.get(City, city_id)
    if not city:
        raise HTTPException(status_code=404, detail='城市不存在')
    count = db.scalar(select(func.count(Village.id)).where(Village.city_id == city.id)) or 0
    if count:
        raise HTTPException(status_code=409, detail='该城市下仍有村落，不能删除')
    db.delete(city); db.commit()
    return {'message': '城市已删除'}

@router.get('/villages')
def admin_villages(q: str = '', city_id: int | None = None, status: str = '', limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    stmt = select(Village).options(selectinload(Village.city), selectinload(Village.media))
    if q:
        stmt = stmt.where(or_(Village.name.contains(q), Village.source_id.contains(q), Village.location.contains(q)))
    if city_id:
        stmt = stmt.where(Village.city_id == city_id)
    if status:
        stmt = stmt.where(Village.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Village.sort_order, Village.id).offset(offset).limit(limit)).all()
    return {'total': total, 'items': [village_summary(v, include_status=True) for v in rows]}

@router.post('/villages', status_code=201)
def create_village(payload: VillageInput, db: Session = Depends(get_db)):
    if not db.get(City, payload.city_id):
        raise HTTPException(status_code=422, detail='城市不存在')
    if payload.status not in ('draft', 'published'):
        raise HTTPException(status_code=422, detail='status 只能为 draft 或 published')
    village = Village(**payload.model_dump())
    db.add(village)
    try:
        db.commit(); db.refresh(village)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='source_id 或 slug 已存在')
    return village_detail(get_village(db, village.id), include_status=True)

@router.get('/villages/{village_id}')
def admin_village(village_id: int, db: Session = Depends(get_db)):
    return village_detail(get_village(db, village_id), include_html=True, include_status=True)

@router.put('/villages/{village_id}')
def update_village(village_id: int, payload: VillageInput, db: Session = Depends(get_db)):
    village = get_village(db, village_id)
    apply_village(village, payload, db)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='source_id 或 slug 已存在')
    return village_detail(get_village(db, village_id), include_status=True)

@router.patch('/villages/{village_id}/status')
def update_village_status(village_id: int, payload: VillageStatusInput, db: Session = Depends(get_db)):
    if payload.status not in ('draft', 'published'):
        raise HTTPException(status_code=422, detail='status 只能为 draft 或 published')
    village = get_village(db, village_id)
    village.status = payload.status
    db.commit()
    return {'id': village.id, 'status': village.status}

@router.delete('/villages/{village_id}')
def delete_village(village_id: int, db: Session = Depends(get_db)):
    village = get_village(db, village_id)
    db.delete(village); db.commit()
    return {'message': '村落已删除'}

@router.post('/villages/{village_id}/sections', status_code=201)
def create_section(village_id: int, payload: SectionInput, db: Session = Depends(get_db)):
    village = get_village(db, village_id)
    item = VillageSection(village_id=village.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {'id': item.id, 'type': item.type, 'title': item.title, 'sort_order': item.sort_order}

@router.put('/sections/{section_id}')
def update_section(section_id: int, payload: SectionInput, db: Session = Depends(get_db)):
    item = get_section(db, section_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit(); db.refresh(item)
    return {'id': item.id, 'type': item.type, 'title': item.title, 'sort_order': item.sort_order}

@router.delete('/sections/{section_id}')
def delete_section(section_id: int, db: Session = Depends(get_db)):
    item = get_section(db, section_id)
    db.delete(item); db.commit()
    return {'message': '内容模块已删除'}

@router.put('/villages/{village_id}/sections/reorder')
def reorder_sections(village_id: int, payload: ReorderInput, db: Session = Depends(get_db)):
    get_village(db, village_id)
    rows = db.scalars(select(VillageSection).where(VillageSection.village_id == village_id)).all()
    by_id = {x.id: x for x in rows}
    for idx, item_id in enumerate(payload.ids):
        if item_id in by_id:
            by_id[item_id].sort_order = idx
    db.commit()
    return {'message': '排序已更新'}

@router.post('/villages/{village_id}/figures', status_code=201)
def create_figure(village_id: int, payload: FigureInput, db: Session = Depends(get_db)):
    village = get_village(db, village_id)
    item = VillageFigure(village_id=village.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {'id': item.id}

@router.put('/figures/{figure_id}')
def update_figure(figure_id: int, payload: FigureInput, db: Session = Depends(get_db)):
    item = get_figure(db, figure_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit(); return {'id': item.id}

@router.delete('/figures/{figure_id}')
def delete_figure(figure_id: int, db: Session = Depends(get_db)):
    db.delete(get_figure(db, figure_id)); db.commit(); return {'message': '历史人物已删除'}

@router.post('/villages/{village_id}/historic-elements', status_code=201)
def create_historic(village_id: int, payload: HistoricElementInput, db: Session = Depends(get_db)):
    village = get_village(db, village_id)
    item = HistoricElement(village_id=village.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {'id': item.id}

@router.put('/historic-elements/{element_id}')
def update_historic(element_id: int, payload: HistoricElementInput, db: Session = Depends(get_db)):
    item = get_historic(db, element_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit(); return {'id': item.id}

@router.delete('/historic-elements/{element_id}')
def delete_historic(element_id: int, db: Session = Depends(get_db)):
    db.delete(get_historic(db, element_id)); db.commit(); return {'message': '历史环境要素已删除'}

@router.post('/villages/{village_id}/media', status_code=201)
def create_media(village_id: int, payload: MediaInput, db: Session = Depends(get_db)):
    village = get_village(db, village_id)
    item = MediaItem(village_id=village.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {'id': item.id, 'url': item.url, 'media_type': item.media_type}

@router.post('/villages/{village_id}/media/upload', status_code=201)
async def upload_media(
    village_id: int,
    file: UploadFile = File(...),
    title: str = Form(''),
    sort_order: int = Form(0),
    db: Session = Depends(get_db),
):
    village = get_village(db, village_id)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        saved = save_uploaded_image(data, file.content_type or '', village.id, title or Path(file.filename or '').stem)
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    item = MediaItem(
        village_id=village.id,
        url=saved['url'],
        media_type='image',
        title=saved['title'],
        source_file='upload',
        sort_order=sort_order,
    )
    db.add(item)
    try:
        db.commit(); db.refresh(item)
    except Exception:
        db.rollback()
        delete_local_upload(saved['url'])
        raise
    return {
        'id': item.id,
        'url': item.url,
        'title': item.title,
        'media_type': item.media_type,
        'width': saved['width'],
        'height': saved['height'],
        'size': saved['size'],
    }


@router.put('/media/{media_id}')
def update_media(media_id: int, payload: MediaInput, db: Session = Depends(get_db)):
    item = get_media(db, media_id)
    old_url = item.url
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    if old_url != item.url:
        delete_local_upload(old_url)
    return {'id': item.id}

@router.delete('/media/{media_id}')
def delete_media(media_id: int, db: Session = Depends(get_db)):
    item = get_media(db, media_id)
    url = item.url
    db.delete(item)
    db.commit()
    delete_local_upload(url)
    return {'message': '媒体已删除'}

@router.get('/feedback')
def admin_feedback(status: str = '', q: str = '', limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    stmt = select(Feedback)
    if status:
        stmt = stmt.where(Feedback.status == status)
    if q:
        stmt = stmt.where(or_(Feedback.village_name.contains(q), Feedback.city.contains(q), Feedback.message.contains(q), Feedback.email.contains(q)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Feedback.created_at.desc()).offset(offset).limit(limit)).all()
    return {'total': total, 'items': [feedback_payload(x) for x in rows]}

@router.patch('/feedback/{feedback_id}')
def update_feedback(feedback_id: int, payload: FeedbackUpdate, db: Session = Depends(get_db)):
    if payload.status not in ('new', 'processing', 'resolved', 'rejected'):
        raise HTTPException(status_code=422, detail='无效的反馈状态')
    item = db.get(Feedback, feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail='反馈不存在')
    item.status = payload.status
    db.commit(); db.refresh(item)
    return feedback_payload(item)

@router.delete('/feedback/{feedback_id}')
def delete_feedback(feedback_id: int, db: Session = Depends(get_db)):
    item = db.get(Feedback, feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail='反馈不存在')
    db.delete(item); db.commit()
    return {'message': '反馈已删除'}

@router.post('/import/processed')
def import_processed_data(db: Session = Depends(get_db)):
    try:
        counts = import_processed(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f'未找到整理后的数据文件: {exc}')
    return {'message': '数据导入完成', 'counts': counts}
