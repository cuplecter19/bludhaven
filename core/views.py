from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .models import IndexImage, TextBlock, ParallaxConfig, ClockWidgetConfig


def index(request):
    bg_image = IndexImage.objects.filter(
        layer=IndexImage.LAYER_BACKGROUND, is_active=True
    ).first()
    main_images = IndexImage.objects.filter(
        layer=IndexImage.LAYER_MAIN, is_active=True
    )
    stickers = IndexImage.objects.filter(
        layer=IndexImage.LAYER_STICKER, is_active=True
    ).order_by('z_index')
    text_blocks = TextBlock.objects.filter(is_active=True)

    parallax_cfg = ParallaxConfig.objects.first() or ParallaxConfig()
    clock_cfg    = ClockWidgetConfig.objects.first() or ClockWidgetConfig()

    context = {
        'bg_image':     bg_image,
        'main_images':  main_images,
        'stickers':     stickers,
        'text_blocks':  text_blocks,
        'parallax_cfg': parallax_cfg,
        'clock_cfg':    clock_cfg,
        'is_admin':     request.user.is_superuser,
    }
    return render(request, 'core/index.html', context)


# ── Sticker APIs ─────────────────────────────────────────────────────────────

@api_view(['POST', 'PATCH'])
@permission_classes([IsAdminUser])
def sticker_move(request, pk):
    sticker = get_object_or_404(IndexImage, pk=pk, layer=IndexImage.LAYER_STICKER)
    pos_left = request.data.get('pos_left')
    pos_top  = request.data.get('pos_top')
    if pos_left is not None:
        sticker.pos_left = pos_left
    if pos_top is not None:
        sticker.pos_top = pos_top
    sticker.save(update_fields=['pos_left', 'pos_top'])
    return Response({'ok': True, 'data': {'pos_left': sticker.pos_left, 'pos_top': sticker.pos_top}})


@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAdminUser])
def sticker_update(request, pk):
    sticker = get_object_or_404(IndexImage, pk=pk, layer=IndexImage.LAYER_STICKER)
    if request.method == 'GET':
        return Response({'ok': True, 'data': _sticker_data(sticker)})
    fields = ['pos_left', 'pos_top', 'width', 'height', 'rotate', 'z_index', 'title', 'is_active']
    updated = []
    for f in fields:
        if f in request.data:
            setattr(sticker, f, request.data[f])
            updated.append(f)
    if updated:
        sticker.save(update_fields=updated)
    return Response({'ok': True, 'data': _sticker_data(sticker)})


@api_view(['DELETE', 'POST'])
@permission_classes([IsAdminUser])
def sticker_delete(request, pk):
    sticker = get_object_or_404(IndexImage, pk=pk, layer=IndexImage.LAYER_STICKER)
    sticker.delete()
    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sticker_add(request):
    image_file = request.FILES.get('image')
    if not image_file:
        return Response({'ok': False, 'error': 'image file required'}, status=status.HTTP_400_BAD_REQUEST)
    sticker = IndexImage(
        title=request.data.get('title', ''),
        layer=IndexImage.LAYER_STICKER,
        pos_left=request.data.get('pos_left', '50%'),
        pos_top=request.data.get('pos_top', '50%'),
        width=request.data.get('width', '160px'),
        height=request.data.get('height', 'auto'),
        rotate=int(request.data.get('rotate', 0)),
        z_index=int(request.data.get('z_index', 10)),
    )
    sticker.image = image_file
    sticker.save()
    return Response({'ok': True, 'data': _sticker_data(sticker)}, status=status.HTTP_201_CREATED)


# ── TextBlock API ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAdminUser])
def textblock_update(request, pk):
    tb = get_object_or_404(TextBlock, pk=pk)
    if request.method == 'GET':
        return Response({'ok': True, 'data': _textblock_data(tb)})
    fields = ['content', 'pos_left', 'pos_top', 'font_size', 'color', 'z_index', 'is_active']
    updated = []
    for f in fields:
        if f in request.data:
            setattr(tb, f, request.data[f])
            updated.append(f)
    if updated:
        tb.save(update_fields=updated)
    return Response({'ok': True, 'data': _textblock_data(tb)})


# ── Clock Widget API ──────────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAdminUser])
def clock_update(request):
    cfg = ClockWidgetConfig.objects.first()
    if cfg is None:
        cfg = ClockWidgetConfig()
    if request.method == 'GET':
        return Response({'ok': True, 'data': _clock_data(cfg)})
    fields = ['is_active', 'pos_left', 'pos_top', 'font_size', 'color', 'z_index']
    for f in fields:
        if f in request.data:
            setattr(cfg, f, request.data[f])
    cfg.save()
    return Response({'ok': True, 'data': _clock_data(cfg)})


# ── Parallax Config API ───────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAdminUser])
def parallax_update(request):
    cfg = ParallaxConfig.objects.first()
    if cfg is None:
        cfg = ParallaxConfig()
    if request.method == 'GET':
        return Response({'ok': True, 'data': _parallax_data(cfg)})
    fields = ['speed', 'blur_px', 'overlay_opacity']
    for f in fields:
        if f in request.data:
            setattr(cfg, f, request.data[f])
    cfg.save()
    return Response({'ok': True, 'data': _parallax_data(cfg)})


# ── Layout State API ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def layout_state(request):
    stickers = IndexImage.objects.filter(layer=IndexImage.LAYER_STICKER, is_active=True).order_by('z_index')
    text_blocks = TextBlock.objects.filter(is_active=True)
    parallax_cfg = ParallaxConfig.objects.first() or ParallaxConfig()
    clock_cfg    = ClockWidgetConfig.objects.first() or ClockWidgetConfig()
    return Response({
        'ok': True,
        'data': {
            'stickers':    [_sticker_data(s) for s in stickers],
            'text_blocks': [_textblock_data(tb) for tb in text_blocks],
            'parallax':    _parallax_data(parallax_cfg),
            'clock':       _clock_data(clock_cfg),
        },
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sticker_data(s):
    return {
        'pk':       s.pk,
        'title':    s.title,
        'image':    s.image.url if s.image else None,
        'pos_left': s.pos_left,
        'pos_top':  s.pos_top,
        'width':    s.width,
        'height':   s.height,
        'rotate':   s.rotate,
        'z_index':  s.z_index,
        'is_active': s.is_active,
    }


def _textblock_data(tb):
    return {
        'pk':        tb.pk,
        'position':  tb.position,
        'content':   tb.content,
        'pos_left':  tb.pos_left,
        'pos_top':   tb.pos_top,
        'font_size': tb.font_size,
        'color':     tb.color,
        'z_index':   tb.z_index,
        'is_active': tb.is_active,
    }


def _parallax_data(cfg):
    return {
        'speed':           cfg.speed,
        'blur_px':         cfg.blur_px,
        'overlay_opacity': cfg.overlay_opacity,
    }


def _clock_data(cfg):
    return {
        'is_active': cfg.is_active,
        'pos_left':  cfg.pos_left,
        'pos_top':   cfg.pos_top,
        'font_size': cfg.font_size,
        'color':     cfg.color,
        'z_index':   cfg.z_index,
    }
