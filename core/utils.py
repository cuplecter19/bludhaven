import io
from pathlib import Path
from PIL import Image
from django.core.files.base import ContentFile


def convert_to_webp(image_field_file, quality: int = 82) -> ContentFile:
    """
    Django ImageField 파일 객체를 WebP ContentFile로 변환하여 반환한다.
    원본 확장자는 .webp로 교체된다.
    """
    img = Image.open(image_field_file)
    if img.mode not in ('RGBA', 'RGB'):
        img = img.convert('RGBA')
    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=quality, method=6)
    buf.seek(0)
    stem = Path(image_field_file.name).stem
    return ContentFile(buf.read(), name=f'{stem}.webp')
