from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction

from .models import ShopItem, Purchase, Review, ShopSetting

ALLOWED_IMAGE_TYPES = {'image/png', 'image/webp', 'image/gif', 'image/jpeg'}


@login_required
def shop(request):
    user = request.user
    items = ShopItem.objects.filter(is_active=True)
    recent_purchases = Purchase.objects.filter(user=user).order_by('-purchased_at')[:10]
    reviews = Review.objects.select_related('user').all()
    setting = ShopSetting.get()

    context = {
        'items': items,
        'recent_purchases': recent_purchases,
        'reviews': reviews,
        'setting': setting,
    }
    return render(request, 'shop/shop.html', context)


@login_required
@require_POST
def buy_item(request, item_id):
    item = get_object_or_404(ShopItem, id=item_id, is_active=True)
    user = request.user

    try:
        points_spent = int(request.POST.get('points_spent', 0))
    except (ValueError, TypeError):
        messages.error(request, '구매 금액을 올바르게 입력해주세요.')
        return redirect('shop:shop')

    if points_spent < 1:
        messages.error(request, '구매 금액은 1pt 이상이어야 해요.')
        return redirect('shop:shop')

    if user.points < points_spent:
        messages.error(request, f'포인트가 부족해요. (보유: {user.points}pt)')
        return redirect('shop:shop')

    with transaction.atomic():
        user.points -= points_spent
        user.save(update_fields=['points'])

        Purchase.objects.create(
            user=user,
            item=item,
            points_spent=points_spent,
        )

    messages.success(request, f'"{item.name}" 구매 완료! {points_spent:,}pt를 사용했어요.')
    return redirect('shop:shop')


@staff_member_required
@require_POST
def add_item(request):
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    image = request.FILES.get('image')

    if not name:
        messages.error(request, '아이템 이름은 필수예요.')
        return redirect('shop:shop')

    if image and image.content_type not in ALLOWED_IMAGE_TYPES:
        messages.error(request, 'PNG, WebP, GIF, JPEG 형식만 업로드할 수 있어요.')
        return redirect('shop:shop')

    ShopItem.objects.create(
        name=name,
        description=description,
        image=image,
    )
    messages.success(request, f'"{name}" 아이템이 등록됐어요.')
    return redirect('shop:shop')


@staff_member_required
@require_POST
def delete_item(request, item_id):
    item = get_object_or_404(ShopItem, id=item_id)
    item.is_active = False
    item.save(update_fields=['is_active'])
    messages.success(request, f'"{item.name}" 아이템이 삭제됐어요.')
    return redirect('shop:shop')


@staff_member_required
@require_POST
def update_default_review_image(request):
    image = request.FILES.get('default_review_image')
    if not image:
        messages.error(request, '이미지 파일을 선택해주세요.')
        return redirect('shop:shop')

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        messages.error(request, 'PNG, WebP, GIF, JPEG 형식만 업로드할 수 있어요.')
        return redirect('shop:shop')

    setting = ShopSetting.get()
    setting.default_review_image = image
    setting.save()
    messages.success(request, '기본 후기 이미지가 업데이트됐어요.')
    return redirect('shop:shop')


@login_required
@require_POST
def add_review(request):
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    image = request.FILES.get('image')

    if not title:
        messages.error(request, '제목을 입력해주세요.')
        return redirect('shop:shop')

    if image and image.content_type not in ALLOWED_IMAGE_TYPES:
        messages.error(request, 'PNG, WebP, GIF, JPEG 형식만 업로드할 수 있어요.')
        return redirect('shop:shop')

    Review.objects.create(
        user=request.user,
        title=title,
        content=content,
        image=image or None,
    )
    messages.success(request, '후기가 등록됐어요!')
    return redirect('shop:shop')


@login_required
@require_POST
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    if review.user != request.user and not request.user.is_staff:
        messages.error(request, '삭제 권한이 없어요.')
        return redirect('shop:shop')
    review.delete()
    messages.success(request, '후기가 삭제됐어요.')
    return redirect('shop:shop')