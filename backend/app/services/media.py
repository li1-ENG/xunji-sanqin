from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import secrets

from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import MAX_IMAGE_EDGE, MAX_UPLOAD_BYTES, UPLOAD_DIR

ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


class ImageValidationError(ValueError):
    pass


def save_uploaded_image(data: bytes, content_type: str, village_id: int, title: str = '') -> dict:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ImageValidationError('仅支持 JPG、PNG、WebP 图片。')
    if not data:
        raise ImageValidationError('上传文件为空。')
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageValidationError(f'图片不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB。')
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise ImageValidationError('文件不是有效的图片。')
    if getattr(image, 'is_animated', False):
        raise ImageValidationError('暂不支持动态图片。')
    if image.width < 20 or image.height < 20:
        raise ImageValidationError('图片尺寸过小。')

    image = ImageOps.exif_transpose(image)
    if image.mode in {'RGBA', 'LA'}:
        background = Image.new('RGB', image.size, (250, 248, 244))
        alpha = image.getchannel('A') if image.mode == 'RGBA' else image.getchannel('A')
        background.paste(image.convert('RGB'), mask=alpha)
        image = background
    else:
        image = image.convert('RGB')
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)

    now = datetime.now(timezone.utc)
    relative = Path('villages') / str(village_id) / f'{now:%Y}' / f'{now:%m}' / f'{secrets.token_hex(12)}.webp'
    target = UPLOAD_DIR / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format='WEBP', quality=88, method=6)

    return {
        'url': '/uploads/' + relative.as_posix(),
        'path': target,
        'title': title.strip()[:255],
        'width': image.width,
        'height': image.height,
        'size': target.stat().st_size,
    }


def delete_local_upload(url: str) -> bool:
    if not url or not url.startswith('/uploads/'):
        return False
    relative = url.removeprefix('/uploads/').split('?', 1)[0]
    target = (UPLOAD_DIR / relative).resolve()
    root = UPLOAD_DIR.resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return False
    target.unlink(missing_ok=True)
    return True
