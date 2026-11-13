from pathlib import Path
import json
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ..config import PROCESSED_VILLAGES
from ..models import City, HistoricElement, MediaItem, Village, VillageFigure, VillageSection

def _txt(value, limit=None):
    value = '' if value is None else str(value)
    return value[:limit] if limit else value

def import_processed(db: Session, path: Path | None = None) -> dict:
    source = Path(path) if path else PROCESSED_VILLAGES
    villages_data = json.loads(source.read_text('utf-8'))
    cities_path = source.parent / 'shanxi_cities.json'
    city_rows = json.loads(cities_path.read_text('utf-8')) if cities_path.exists() else []

    counts = {'cities': 0, 'villages': 0, 'sections': 0, 'figures': 0, 'historic_elements': 0, 'media': 0}
    city_by_name = {}
    for row in city_rows:
        city = db.scalar(select(City).where(City.code == row.get('code')))
        if not city:
            city = City(name=_txt(row.get('name'), 40), slug=_txt(row.get('slug'), 40), code=_txt(row.get('code'), 10), sort_order=int(row.get('sort_order', 0) or 0))
            db.add(city); db.flush(); counts['cities'] += 1
        else:
            city.name = _txt(row.get('name'), 40); city.slug = _txt(row.get('slug'), 40); city.sort_order = int(row.get('sort_order', 0) or 0)
        city_by_name[city.name] = city

    for data in villages_data:
        city_name = _txt(data.get('city'), 40)
        city = city_by_name.get(city_name)
        if not city:
            city = db.scalar(select(City).where(City.name == city_name))
        if not city:
            continue
        village = db.scalar(select(Village).where(Village.source_id == str(data.get('id'))))
        if not village:
            village = Village(source_id=str(data.get('id')), name=_txt(data.get('name'), 120), slug=str(data.get('id')), city_id=city.id)
            db.add(village); db.flush(); counts['villages'] += 1
        village.name = _txt(data.get('name'), 120)
        village.slug = str(data.get('id'))
        village.city_id = city.id
        village.location = _txt(data.get('location'), 255)
        village.summary = _txt(data.get('summary') or '')
        village.cover_image = _txt(data.get('cover_image') or '')
        village.description_html = _txt(data.get('description_html') or '')
        village.description_text = _txt(data.get('description_text') or '')
        village.attributes_json = data.get('attributes') or {}
        village.status = 'published'
        village.source_url = _txt(data.get('source_url') or '')
        village.source_site = _txt(data.get('source_site') or '')

        db.execute(delete(VillageSection).where(VillageSection.village_id == village.id))
        db.execute(delete(VillageFigure).where(VillageFigure.village_id == village.id))
        db.execute(delete(HistoricElement).where(HistoricElement.village_id == village.id))
        db.execute(delete(MediaItem).where(MediaItem.village_id == village.id))

        for idx, item in enumerate(data.get('sections') or []):
            section = VillageSection(
                village_id=village.id, type=_txt(item.get('type'), 40), title=_txt(item.get('title'), 120),
                content_html=_txt(item.get('content_html') or ''), content_text=_txt(item.get('content_text') or ''),
                images_json=item.get('images') or [], sort_order=idx,
                source_file=_txt(item.get('source_file'), 80), source_url=_txt(item.get('source_url') or ''),
            )
            db.add(section); counts['sections'] += 1

        for idx, item in enumerate(data.get('figures') or []):
            db.add(VillageFigure(
                village_id=village.id, name=_txt(item.get('name'), 120),
                content_html=_txt(item.get('content_html') or ''), content_text=_txt(item.get('content_text') or ''),
                sort_order=idx, source_url=_txt(item.get('source_url') or ''),
            )); counts['figures'] += 1

        for idx, item in enumerate(data.get('historic_elements') or []):
            db.add(HistoricElement(
                village_id=village.id, name=_txt(item.get('name'), 120), code=_txt(item.get('code'), 40),
                images_json=item.get('images') or [], sort_order=idx, source_url=_txt(item.get('source_url') or ''),
            )); counts['historic_elements'] += 1

        media_seen = set()
        def add_media(url, media_type, title, source_file, source_url, sort_order):
            url = _txt(url or '')
            key = (media_type, url)
            if not url or key in media_seen:
                return
            media_seen.add(key)
            db.add(MediaItem(
                village_id=village.id, url=url, media_type=media_type, title=_txt(title, 255),
                source_file=_txt(source_file, 80), source_url=_txt(source_url or ''), sort_order=sort_order,
            ))
            counts['media'] += 1
        for idx, item in enumerate(data.get('images') or []):
            add_media(item.get('url'), 'image', item.get('title'), item.get('source_file'), data.get('source_url'), idx)
        for idx, item in enumerate(data.get('videos') or []):
            add_media(item.get('url'), item.get('kind') or 'video', item.get('title'), item.get('source_file'), data.get('source_url'), 10000 + idx)
    db.commit()
    return counts

def seed_admin_from_config(db: Session):
    from ..security import ensure_default_admin
    return ensure_default_admin(db)
