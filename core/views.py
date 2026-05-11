from django.shortcuts import render
from .models import IndexImage, TextBlock


def index(request):
    bg_image = IndexImage.objects.filter(
        layer=IndexImage.LAYER_BACKGROUND, is_active=True
    ).first()
    main_images = IndexImage.objects.filter(
        layer=IndexImage.LAYER_MAIN, is_active=True
    )[:3]

    text_blocks = {
        tb.position: tb.content
        for tb in TextBlock.objects.filter(is_active=True)
    }

    context = {
        'bg_image': bg_image,
        'main_images': main_images,
        'text_blocks': text_blocks,
    }
    return render(request, 'core/index.html', context)
