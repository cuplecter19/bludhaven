import hashlib
import io
import logging
import os
import tempfile
import urllib.parse
import urllib.request
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import CustomFont, EditorRevision, MediaAsset, PageScene, SceneLayer

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'}

MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG': 'image/png',
    b'RIFF': 'image/webp',
    b'\x00\x00\x00': None,   # avif/heic starts with ftyp box – checked separately
    b'GIF8': 'image/gif',
}


TIER_BASE_MAP = {
    -3: 100,
    -2: 200,
    -1: 300,
     0: 400,
     1: 500,
     2: 600,
     3: 700,
     4: 800,
}

STICKER_Z_MIN = 0
STICKER_Z_MAX = 999
ALLOWED_FONT_EXTENSIONS = {'.woff', '.woff2', '.ttf', '.otf'}
FONT_FORMAT_MAP = {
    '.woff': 'woff',
    '.woff2': 'woff2',
    '.ttf': 'truetype',
    '.otf': 'opentype',
}


def healthz(request):
    return HttpResponse('ok', content_type='text/plain')


def index(request):
    return render(request, 'core/index.html', {'is_admin': request.user.is_staff})


@api_view(['GET'])
def active_scene(request):
    scene = PageScene.objects.filter(is_active=True).prefetch_related('layers').first()
    if scene is None:
        return Response({'ok': True, 'data': fallback_scene()}, status=status.HTTP_200_OK)
    return Response({'ok': True, 'data': serialize_scene(scene)}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_profile(request):
    user = request.user
    profile_image_url = request.build_absolute_uri(user.profile_image.url) if user.profile_image else None
    return Response(
        {
            'ok': True,
            'data': {
                'nickname': user.nickname,
                'points': user.points,
                'profile_image_url': profile_image_url,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_layer(request):
    scene_id = request.data.get('scene_id')
    layer_type = request.data.get('layer_type')
    if not scene_id or not layer_type:
        return bad_request('INVALID_REQUEST', 'scene_id and layer_type are required')

    scene = get_object_or_404(PageScene, pk=scene_id)
    try:
        parsed = parse_layer_numeric_fields(request.data)
        if layer_type == SceneLayer.TYPE_STICKER:
            validate_sticker_z(parsed.get('z_index', 0))
        layer = SceneLayer(
            scene=scene,
            layer_type=layer_type,
            z_index=parsed['z_index'],
            enabled=bool(request.data.get('enabled', True)),
            x=parsed['x'],
            y=parsed['y'],
            width=parsed['width'],
            height=parsed['height'],
            rotation_deg=parsed['rotation_deg'],
            scale=parsed['scale'],
            opacity=parsed['opacity'],
            settings_json=request.data.get('settings_json') or {},
        )
        layer.save()
    except (ValidationError, ValueError):
        return bad_request('VALIDATION_FAILED', '')
    except Exception:
        return bad_request('VALIDATION_FAILED', 'Invalid layer payload')

    return Response({'ok': True, 'data': serialize_layer(layer)}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def patch_layer(request, layer_id):
    layer = get_object_or_404(SceneLayer, pk=layer_id)
    if 'layer_tier' in request.data:
        requested = int(request.data.get('layer_tier'))
        expected = SceneLayer.TYPE_TIER_MAP[layer.layer_type]
        if requested != expected:
            return bad_request('INVALID_TIER', f'layer_tier for {layer.layer_type} must be {expected}')

    mutable_fields = [
        'layer_type', 'z_index', 'enabled', 'x', 'y', 'width', 'height', 'rotation_deg', 'scale', 'opacity', 'settings_json'
    ]
    try:
        for field in mutable_fields:
            if field not in request.data:
                continue
            value = request.data[field]
            if field in ('z_index',):
                value = int(value)
                if (request.data.get('layer_type') or layer.layer_type) == SceneLayer.TYPE_STICKER:
                    validate_sticker_z(value)
            elif field in ('x', 'y', 'width', 'height', 'rotation_deg', 'scale', 'opacity'):
                value = float(value)
            setattr(layer, field, value)
        layer.save()
    except (ValidationError, ValueError):
        return bad_request('VALIDATION_FAILED', '')
    except Exception:
        return bad_request('VALIDATION_FAILED', 'Invalid layer patch')

    return Response({'ok': True, 'data': serialize_layer(layer)})


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_layer(request, layer_id):
    layer = get_object_or_404(SceneLayer, pk=layer_id)
    layer.delete()
    return Response({'ok': True}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reorder_layers(request):
    orders = request.data.get('orders')
    if not isinstance(orders, list):
        return bad_request('INVALID_REQUEST', 'orders must be a list')

    updated_ids = []
    try:
        with transaction.atomic():
            for item in orders:
                layer = SceneLayer.objects.select_for_update().get(pk=int(item['id']))
                layer.z_index = int(item['z_index'])
                layer.save(update_fields=['z_index', 'updated_at'])
                updated_ids.append(layer.id)
    except SceneLayer.DoesNotExist:
        raise Http404
    except (ValidationError, ValueError):
        return bad_request('VALIDATION_FAILED', '')
    except Exception:
        return bad_request('VALIDATION_FAILED', 'Invalid reorder payload')

    layers = list(SceneLayer.objects.filter(id__in=updated_ids))
    return Response({'ok': True, 'data': [serialize_layer(l) for l in layers]})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_asset(request):
    file = request.FILES.get('file')
    kind = request.data.get('kind', 'generic')
    if not file:
        return bad_request('INVALID_REQUEST', 'file is required')

    try:
        validate_upload(file)
    except ValueError:
        return bad_request('FILE_TOO_LARGE', '')

    original_tmp_path = None
    variants_payload = {}
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='-upload') as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            original_tmp_path = tmp.name

        with open(original_tmp_path, 'rb') as f:
            original_bytes = f.read()

        try:
            validate_file_magic_bytes(original_bytes, file.name, file.content_type)
        except ValueError:
            return bad_request('UNSUPPORTED_FORMAT', '')

        image = Image.open(io.BytesIO(original_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGBA')

        hash_sha = hashlib.sha256(original_bytes).hexdigest()
        variants = generate_variants(image)

        base_key = f"core/assets/{timezone.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}"
        saved_paths = {}
        for name, variant in variants.items():
            webp_bytes = transcode_to_webp(variant, quality=82)
            webp_path = default_storage.save(f'{base_key}_{name}.webp', ContentFile(webp_bytes))
            saved_paths[f'{name}_webp'] = webp_path
            try:
                avif_bytes = transcode_to_avif(variant, quality=48)
                avif_path = default_storage.save(f'{base_key}_{name}.avif', ContentFile(avif_bytes))
                saved_paths[f'{name}_avif'] = avif_path
            except Exception as avif_exc:
                logger.warning(
                    'AVIF transcode failed for variant=%s name=%s mime=%s: %s',
                    name, file.name, file.content_type, avif_exc,
                )

        media = MediaAsset.objects.create(
            kind=kind,
            mime_type=file.content_type or 'application/octet-stream',
            storage_path=saved_paths.get('full_webp') or next(iter(saved_paths.values())),
            width=image.width,
            height=image.height,
            bytes=len(original_bytes),
            hash_sha256=hash_sha,
            original_deleted_at=timezone.now(),
        )
        variants_payload = {
            k: default_storage.url(v) for k, v in saved_paths.items()
        }
    except UnidentifiedImageError:
        return bad_request('UNSUPPORTED_FORMAT', '')
    except OSError as os_exc:
        logger.error('Image transcode failed for %s: %s', file.name, os_exc)
        return bad_request('TRANSCODE_FAILED', '')
    except Exception as exc:
        logger.error('Asset upload failed for %s: %s', file.name, exc)
        return bad_request('UPLOAD_FAILED', '')
    finally:
        if original_tmp_path:
            purge_original(original_tmp_path)

    return Response(
        {'ok': True, 'data': {'asset': serialize_asset(media), 'variants': variants_payload}},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_asset_from_url(request):
    url = (request.data.get('url') or '').strip()
    kind = request.data.get('kind', 'generic')
    if not url:
        return bad_request('INVALID_REQUEST', 'url is required')

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return bad_request('INVALID_REQUEST', 'url must use http or https')

    max_bytes = 15 * 1024 * 1024
    original_bytes = None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            original_bytes = resp.read(max_bytes + 1)
    except Exception as exc:
        logger.warning('URL asset fetch failed for %s: %s', url, exc)
        return bad_request('FETCH_FAILED', '')

    if len(original_bytes) > max_bytes:
        return bad_request('FILE_TOO_LARGE', '')

    filename = os.path.basename(parsed.path) or 'image'
    try:
        validate_file_magic_bytes(original_bytes, filename, '')
    except ValueError:
        return bad_request('UNSUPPORTED_FORMAT', '')

    variants_payload = {}
    try:
        image = Image.open(io.BytesIO(original_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGBA')

        hash_sha = hashlib.sha256(original_bytes).hexdigest()
        variants = generate_variants(image)

        base_key = f"core/assets/{timezone.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}"
        saved_paths = {}
        for name, variant in variants.items():
            webp_bytes = transcode_to_webp(variant, quality=82)
            webp_path = default_storage.save(f'{base_key}_{name}.webp', ContentFile(webp_bytes))
            saved_paths[f'{name}_webp'] = webp_path
            try:
                avif_bytes = transcode_to_avif(variant, quality=48)
                avif_path = default_storage.save(f'{base_key}_{name}.avif', ContentFile(avif_bytes))
                saved_paths[f'{name}_avif'] = avif_path
            except Exception as avif_exc:
                logger.warning(
                    'AVIF transcode failed for variant=%s url=%s: %s',
                    name, url, avif_exc,
                )

        media = MediaAsset.objects.create(
            kind=kind,
            mime_type='image/webp',
            storage_path=saved_paths.get('full_webp') or next(iter(saved_paths.values())),
            width=image.width,
            height=image.height,
            bytes=len(original_bytes),
            hash_sha256=hash_sha,
            original_deleted_at=timezone.now(),
        )
        variants_payload = {
            k: default_storage.url(v) for k, v in saved_paths.items()
        }
    except UnidentifiedImageError:
        return bad_request('UNSUPPORTED_FORMAT', '')
    except OSError as os_exc:
        logger.error('Image transcode failed for url %s: %s', url, os_exc)
        return bad_request('TRANSCODE_FAILED', '')
    except Exception as exc:
        logger.error('Asset URL upload failed for %s: %s', url, exc)
        return bad_request('UPLOAD_FAILED', '')

    return Response(
        {'ok': True, 'data': {'asset': serialize_asset(media), 'variants': variants_payload}},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_revision(request):
    scene_id = request.data.get('scene_id')
    if not scene_id:
        return bad_request('INVALID_REQUEST', 'scene_id is required')
    scene = get_object_or_404(PageScene, pk=scene_id)

    snapshot = request.data.get('snapshot_json')
    if not snapshot:
        snapshot = serialize_scene(scene)

    revision = EditorRevision.objects.create(scene=scene, snapshot_json=snapshot, author=request.user)
    return Response({'ok': True, 'data': {'id': revision.id, 'created_at': revision.created_at.isoformat()}})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def restore_revision(request, revision_id):
    revision = get_object_or_404(EditorRevision, pk=revision_id)
    snapshot = revision.snapshot_json or {}
    layers = snapshot.get('layers', [])

    try:
        with transaction.atomic():
            revision.scene.layers.all().delete()
            for item in layers:
                SceneLayer.objects.create(
                    scene=revision.scene,
                    layer_type=item['layer_type'],
                    layer_tier=SceneLayer.TYPE_TIER_MAP[item['layer_type']],
                    z_index=item.get('z_index', 0),
                    enabled=item.get('enabled', True),
                    x=item.get('x', 0),
                    y=item.get('y', 0),
                    width=item.get('width', 200),
                    height=item.get('height', 200),
                    rotation_deg=item.get('rotation_deg', 0),
                    scale=item.get('scale', 1),
                    opacity=item.get('opacity', 1),
                    settings_json=item.get('settings_json') or {},
                )
    except (ValidationError, ValueError):
        return bad_request('RESTORE_FAILED', '')
    except Exception:
        return bad_request('RESTORE_FAILED', 'Revision restore failed')

    return Response({'ok': True, 'data': serialize_scene(revision.scene)})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def editor_scene_list(request):
    scenes = PageScene.objects.all().order_by('-is_active', 'id')
    return Response({'ok': True, 'data': [serialize_scene_summary(s) for s in scenes]})

# 기존 editor_scene_list 뷰 아래에 추가

@api_view(['GET'])
@permission_classes([IsAdminUser])
def asset_list(request):
    kind = request.GET.get('kind')  # ?kind=background 등, 없으면 전체
    qs = MediaAsset.objects.all().order_by('-created_at')
    if kind:
        qs = qs.filter(kind=kind)
    data = []
    for asset in qs:
        thumb_path = None
        # thumb 변형을 우선, 없으면 full 사용
        # storage_path는 full_webp 경로이므로 thumb 경로를 추론
        base = asset.storage_path.replace('_full.webp', '')
        thumb_candidate = f'{base}_thumb.webp'
        if default_storage.exists(thumb_candidate):
            thumb_path = default_storage.url(thumb_candidate)
        else:
            thumb_path = default_storage.url(asset.storage_path)

        data.append({
            **serialize_asset(asset),
            'thumb_url': thumb_path,
            'full_url': default_storage.url(asset.storage_path),
        })
    return Response({'ok': True, 'data': data})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def editor_font_list(request):
    fonts = CustomFont.objects.all().order_by('name', 'id')
    return Response({'ok': True, 'data': [serialize_custom_font(font) for font in fonts]})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def register_font_url(request):
    name = (request.data.get('name') or '').strip()
    font_family = (request.data.get('font_family') or '').strip()
    url = (request.data.get('url') or '').strip()
    if not name or not font_family or not url:
        return bad_request('INVALID_REQUEST', 'name, font_family and url are required')

    font, _ = CustomFont.objects.get_or_create(
        name=name,
        defaults={
            'font_family': font_family,
            'source_type': CustomFont.SOURCE_URL,
            'url': url,
        },
    )
    if font.source_type == CustomFont.SOURCE_UPLOAD and font.file_path:
        try:
            if default_storage.exists(font.file_path):
                default_storage.delete(font.file_path)
        except Exception as exc:
            logger.warning('Failed to delete previous font file %s: %s', font.file_path, exc)
    font.font_family = font_family
    font.source_type = CustomFont.SOURCE_URL
    font.url = url
    font.file_path = ''
    font.format = ''
    font.save()
    return Response({'ok': True, 'data': serialize_custom_font(font)}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_font(request):
    file = request.FILES.get('file')
    name = (request.data.get('name') or '').strip()
    font_family = (request.data.get('font_family') or '').strip()
    if not file or not name or not font_family:
        return bad_request('INVALID_REQUEST', 'file, name and font_family are required')

    ext = os.path.splitext(file.name or '')[1].lower()
    if ext not in ALLOWED_FONT_EXTENSIONS:
        return bad_request('INVALID_REQUEST', 'unsupported font extension')

    storage_path = default_storage.save(f'core/fonts/{uuid.uuid4().hex}{ext}', ContentFile(file.read()))
    font, _ = CustomFont.objects.get_or_create(
        name=name,
        defaults={
            'font_family': font_family,
            'source_type': CustomFont.SOURCE_UPLOAD,
            'file_path': storage_path,
            'format': FONT_FORMAT_MAP[ext],
        },
    )

    previous_file_path = font.file_path if font.file_path and font.file_path != storage_path else ''
    if previous_file_path:
        try:
            if default_storage.exists(previous_file_path):
                default_storage.delete(previous_file_path)
        except Exception as exc:
            logger.warning('Failed to delete previous font file %s: %s', previous_file_path, exc)

    font.font_family = font_family
    font.source_type = CustomFont.SOURCE_UPLOAD
    font.url = ''
    font.file_path = storage_path
    font.format = FONT_FORMAT_MAP[ext]
    font.save()
    return Response({'ok': True, 'data': serialize_custom_font(font)}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_scene(request):
    name = request.data.get('name', 'Untitled Scene').strip() or 'Untitled Scene'
    viewport_mode = request.data.get('viewport_mode', PageScene.VIEWPORT_BOTH)
    is_active = bool(request.data.get('is_active', False))

    with transaction.atomic():
        if is_active:
            PageScene.objects.filter(is_active=True).update(is_active=False)
        scene = PageScene.objects.create(name=name, viewport_mode=viewport_mode, is_active=is_active)
    return Response({'ok': True, 'data': serialize_scene(scene)}, status=status.HTTP_201_CREATED)

@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_asset(request, asset_id):
    asset = get_object_or_404(MediaAsset, pk=asset_id)

    # storage에서 실제 파일 삭제 (모든 variant)
    base = asset.storage_path  # ex) core/assets/2026/05/13/abc123_full.webp
    stem = base.replace('_full.webp', '').replace('_full.avif', '')
    suffixes = [
        '_full.webp', '_full.avif',
        '_large.webp', '_large.avif',
        '_medium.webp', '_medium.avif',
        '_thumb.webp', '_thumb.avif',
    ]
    for suffix in suffixes:
        path = f'{stem}{suffix}'
        try:
            if default_storage.exists(path):
                default_storage.delete(path)
        except Exception as e:
            logger.warning('Failed to delete storage file %s: %s', path, e)

    asset.delete()
    return Response({'ok': True}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_font(request, font_id):
    font = get_object_or_404(CustomFont, pk=font_id)
    if font.file_path:
        try:
            if default_storage.exists(font.file_path):
                default_storage.delete(font.file_path)
        except Exception as exc:
            logger.warning('Failed to delete font file %s: %s', font.file_path, exc)
    font.delete()
    return Response({'ok': True}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def patch_scene(request, scene_id):
    scene = get_object_or_404(PageScene, pk=scene_id)
    if 'name' in request.data:
        scene.name = (request.data.get('name') or '').strip() or scene.name
    if 'viewport_mode' in request.data:
        scene.viewport_mode = request.data.get('viewport_mode')
    if 'is_active' in request.data:
        active = bool(request.data.get('is_active'))
        if active:
            PageScene.objects.filter(is_active=True).exclude(pk=scene.id).update(is_active=False)
        scene.is_active = active
    scene.save()
    return Response({'ok': True, 'data': serialize_scene(scene)})


def fallback_scene():
    return {
        'id': None,
        'name': 'Fallback Scene',
        'is_active': True,
        'viewport_mode': 'both',
        'layers': [
            {
                'id': 'fallback-text',
                'layer_type': 'text',
                'layer_tier': 1,
                'z_index': 0,
                'enabled': True,
                'x': 40,
                'y': 40,
                'width': 420,
                'height': 120,
                'rotation_deg': 0,
                'scale': 1,
                'opacity': 1,
                'settings_json': {'text': '씬이 비어있습니다. 관리자에서 레이어를 추가하세요.'},
                'render_z_index': TIER_BASE_MAP[1],
            }
        ],
    }


def serialize_scene_summary(scene):
    return {
        'id': scene.id,
        'name': scene.name,
        'is_active': scene.is_active,
        'viewport_mode': scene.viewport_mode,
        'created_at': scene.created_at.isoformat(),
        'updated_at': scene.updated_at.isoformat(),
    }


def serialize_scene(scene):
    layer_payload = [serialize_layer(layer) for layer in scene.layers.filter(enabled=True).order_by('layer_tier', 'z_index', 'id')]
    return {
        'id': scene.id,
        'name': scene.name,
        'is_active': scene.is_active,
        'viewport_mode': scene.viewport_mode,
        'layers': layer_payload,
        'created_at': scene.created_at.isoformat(),
        'updated_at': scene.updated_at.isoformat(),
    }


def serialize_layer(layer):
    return {
        'id': layer.id,
        'scene_id': layer.scene_id,
        'layer_type': layer.layer_type,
        'layer_tier': layer.layer_tier,
        'z_index': layer.z_index,
        'enabled': layer.enabled,
        'x': layer.x,
        'y': layer.y,
        'width': layer.width,
        'height': layer.height,
        'rotation_deg': layer.rotation_deg,
        'scale': layer.scale,
        'opacity': layer.opacity,
        'settings_json': layer.settings_json,
        'render_z_index': TIER_BASE_MAP[layer.layer_tier] + layer.z_index,
        'created_at': layer.created_at.isoformat(),
        'updated_at': layer.updated_at.isoformat(),
    }


def serialize_asset(asset):
    return {
        'id': asset.id,
        'kind': asset.kind,
        'mime_type': asset.mime_type,
        'storage_path': asset.storage_path,
        'width': asset.width,
        'height': asset.height,
        'bytes': asset.bytes,
        'hash_sha256': asset.hash_sha256,
        'original_deleted_at': asset.original_deleted_at.isoformat() if asset.original_deleted_at else None,
        'created_at': asset.created_at.isoformat(),
    }


def serialize_custom_font(font):
    if font.source_type == CustomFont.SOURCE_UPLOAD and font.file_path:
        try:
            font_url = default_storage.url(font.file_path)
        except Exception:
            font_url = ''
    else:
        font_url = font.url
    return {
        'id': font.id,
        'name': font.name,
        'font_family': font.font_family,
        'source_type': font.source_type,
        'url': font_url,
        'file_path': font.file_path,
        'format': font.format,
        'created_at': font.created_at.isoformat(),
    }


def bad_request(error_code, message):
    safe_messages = {
        'INVALID_REQUEST': 'Invalid request payload',
        'INVALID_TIER': 'Invalid layer tier request',
        'VALIDATION_FAILED': 'Validation failed',
        'FILE_TOO_LARGE': 'File exceeds size limit',
        'UNSUPPORTED_FORMAT': 'Unsupported image format',
        'TRANSCODE_FAILED': 'Image transcode failed',
        'UPLOAD_FAILED': 'Asset upload failed',
        'FETCH_FAILED': 'Failed to fetch image from URL',
        'RESTORE_FAILED': 'Revision restore failed',
    }
    return Response(
        {
            'ok': False,
            'error_code': error_code,
            'error': safe_messages.get(error_code, 'Request failed'),
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def validate_upload(file):
    max_bytes = 15 * 1024 * 1024
    if file.size > max_bytes:
        raise ValueError('File exceeds size limit')


def validate_file_magic_bytes(data: bytes, filename: str, content_type: str) -> None:
    header = data[:12]
    # JPEG
    if header[:3] == b'\xff\xd8\xff':
        return
    # PNG
    if header[:4] == b'\x89PNG':
        return
    # GIF
    if header[:4] in (b'GIF8', b'GIF9'):
        return
    # WebP: RIFF....WEBP
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return
    # AVIF / HEIF: ftyp box (bytes 4-8)
    if header[4:8] in (b'ftyp', b'mif1', b'heic', b'heix', b'avif', b'avis'):
        return
    raise ValueError(f'Unsupported file format: {filename!r} ({content_type})')


def parse_layer_numeric_fields(data):
    parsed = {
        'z_index':      int(data.get('z_index', 0)),
        'x':            float(data.get('x', 0)),
        'y':            float(data.get('y', 0)),
        'width':        float(data.get('width', 200)),
        'height':       float(data.get('height', 200)),
        'rotation_deg': float(data.get('rotation_deg', 0)),
        'scale':        float(data.get('scale', 1)),
        'opacity':      float(data.get('opacity', 1)),
    }
    # x, y는 음수 허용 (화면 밖 배치, 패럴랙스 오프셋 등)
    for axis in ('width', 'height'):
        if parsed[axis] < 0:
            raise ValueError(f'{axis} must be >= 0')
    return parsed


def validate_sticker_z(value):
    if not (STICKER_Z_MIN <= value <= STICKER_Z_MAX):
        raise ValueError(f'sticker z_index must be in range {STICKER_Z_MIN}..{STICKER_Z_MAX}')


def transcode_to_webp(image, quality):
    output = io.BytesIO()
    img = image.copy()
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')
    img.save(output, format='WEBP', quality=quality, method=6)
    return output.getvalue()


def transcode_to_avif(image, quality):
    output = io.BytesIO()
    img = image.copy()
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')
    img.save(output, format='AVIF', quality=quality)
    return output.getvalue()


def generate_variants(image):
    variants = {'full': image.copy()}
    limits = {
        'large': 1920,
        'medium': 1280,
        'thumb': 512,
    }
    for key, max_side in limits.items():
        variant = image.copy()
        variant.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        variants[key] = variant
    return variants


def purge_original(temp_path):
    try:
        os.remove(temp_path)
    except FileNotFoundError:
        pass
