import io
import os
from pathlib import Path

from PIL import Image, ImageOps
from django.core.files.base import ContentFile


def convert_to_webp(image_field_file, quality: int = 82) -> ContentFile:
    image = Image.open(image_field_file)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ('RGBA', 'RGB'):
        image = image.convert('RGBA')
    buf = io.BytesIO()
    image.save(buf, format='WEBP', quality=quality, method=6)
    buf.seek(0)
    stem = Path(image_field_file.name).stem
    return ContentFile(buf.read(), name=f'{stem}.webp')


def purge_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        return
