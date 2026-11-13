from pathlib import Path
from ..models import City, Feedback, Village

CITY_GALLERY_DIR = Path(__file__).resolve().parents[1] / 'static' / 'city-gallery'

def city_payload(city: City, village_count: int | None = None) -> dict:
    data = {'id': city.id, 'name': city.name, 'slug': city.slug, 'code': city.code, 'sort_order': city.sort_order}
    if village_count is not None:
        data['village_count'] = village_count
        data['has_data'] = village_count > 0
    return data

def media_payload(item) -> dict:
    return {
        'id': item.id, 'url': item.url, 'media_type': item.media_type, 'title': item.title,
        'source_file': item.source_file, 'source_url': item.source_url, 'sort_order': item.sort_order,
    }

def section_payload(item, include_html: bool = True) -> dict:
    data = {
        'id': item.id, 'type': item.type, 'title': item.title, 'content_text': item.content_text,
        'images': item.images_json or [], 'sort_order': item.sort_order, 'source_file': item.source_file,
        'source_url': item.source_url,
    }
    if include_html:
        data['content_html'] = item.content_html
    return data

def village_summary(v: Village, include_status: bool = False) -> dict:
    media = sorted(v.media, key=lambda x: x.sort_order)
    images = [x.url for x in media if x.media_type == 'image']
    banner_images = [
        x for x in media
        if x.media_type == 'image'
        and ('/b_' in (x.url or '') or (x.source_file or '').endswith('banner'))
    ]
    non_photo_words = ('\u7ebf\u8def', '\u5730\u56fe', '\u5e73\u9762', '\u793a\u610f', '\u5206\u5e03', '\u5bfc\u89c8', '\u4ea4\u901a')
    photo_banners = [
        x for x in banner_images
        if not any(word in (x.title or '') for word in non_photo_words)
    ]
    gallery_images = photo_banners[:3] if photo_banners else banner_images[:3] if banner_images else [
        x for x in media if x.media_type == 'image'
    ][:3]
    gallery_payload = []
    for index, item in enumerate(gallery_images, 1):
        local_file = CITY_GALLERY_DIR / f'{v.source_id}-{index}.jpg'
        if local_file.exists():
            gallery_payload.append({
                'url': f'/static/city-gallery/{v.source_id}-{index}.jpg',
                'title': item.title,
                'local': True,
            })
    if not gallery_payload and gallery_images:
        item = gallery_images[0]
        gallery_payload.append({'url': item.url, 'title': item.title, 'local': False})
    data = {
        'id': v.id, 'source_id': v.source_id, 'name': v.name, 'slug': v.slug,
        'city': {'id': v.city.id, 'name': v.city.name, 'slug': v.city.slug, 'code': v.city.code},
        'location': v.location, 'cover_image': v.cover_image, 'images': images[:20],
        'gallery_images': gallery_payload,
        'summary': v.summary, 'source_url': v.source_url,
    }
    if include_status:
        data['status'] = v.status
        data['sort_order'] = v.sort_order
    return data

def village_detail(v: Village, include_html: bool = True, include_status: bool = False) -> dict:
    data = {
        'id': v.id, 'source_id': v.source_id, 'name': v.name, 'slug': v.slug,
        'city': {'id': v.city.id, 'name': v.city.name, 'slug': v.city.slug, 'code': v.city.code},
        'location': v.location, 'summary': v.summary, 'cover_image': v.cover_image,
        'description_html': v.description_html if include_html else '', 'description_text': v.description_text,
        'attributes': v.attributes_json or {},
        'sections': [section_payload(x, include_html) for x in sorted(v.sections, key=lambda y: y.sort_order)],
        'figures': [{
            'id': x.id, 'name': x.name, 'content_text': x.content_text,
            'content_html': x.content_html if include_html else '', 'sort_order': x.sort_order, 'source_url': x.source_url,
        } for x in sorted(v.figures, key=lambda y: y.sort_order)],
        'historic_elements': [{
            'id': x.id, 'name': x.name, 'code': x.code, 'images': x.images_json or [],
            'sort_order': x.sort_order, 'source_url': x.source_url,
        } for x in sorted(v.historic_elements, key=lambda y: y.sort_order)],
        'media': [media_payload(x) for x in sorted(v.media, key=lambda y: y.sort_order)],
        'source_url': v.source_url, 'source_site': v.source_site,
    }
    if include_status:
        data['status'] = v.status
        data['sort_order'] = v.sort_order
    return data

def feedback_payload(item: Feedback) -> dict:
    return {
        'id': item.id, 'name': item.name, 'email': item.email, 'category': item.category,
        'village_name': item.village_name, 'city': item.city, 'message': item.message,
        'status': item.status, 'created_at': item.created_at.isoformat(), 'updated_at': item.updated_at.isoformat(),
    }

