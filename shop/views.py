import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import localdate

from .models import ShopItem, Purchase, CreditLog
from accounts.models import Inventory

ALLOWED_IMAGE_TYPES = {'image/png', 'image/webp', 'image/gif', 'image/jpeg'}


@login_required
def shop(request):
    user = request.user
    today = localdate()
    items = ShopItem.objects.filter(is_active=True)
    recent_purchases = Purchase.objects.filter(user=user).order_by('-purchased_at')[:10]
    credit_logs = CreditLog.objects.filter(user=user).order_by('-spent_at')[:10]

    this_month_spent = CreditLog.objects.filter(
        user=user,
        spent_at__year=today.year,
        spent_at__month=today.month,
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'items': items,
        'recent_purchases': recent_purchases,
        'credit_logs': credit_logs,
        'this_month_spent': this_month_spent,
    }
    return render(request, 'shop/shop.html', context)


@login_required
@require_POST
def buy_item(request, item_id):
    item = get_object_or_404(ShopItem, id=item_id, is_active=True)
    user = request.user

    if user.points < item.price_points:
        messages.error(request, f'포인트가 부족해요. (보유: {user.points}pt)')
        return redirect('shop:shop')

    with transaction.atomic():
        user.points -= item.price_points

        if item.item_type == 'credit':
            # 크레딧권: 즉시 크레딧 지급
            credits_gained = item.credit_amount or 0
            user.credits += credits_gained
            user.save(update_fields=['points', 'credits'])

            Purchase.objects.create(
                user=user,
                item=item,
                points_spent=item.price_points,
                credits_gained=credits_gained,
            )
            messages.success(request, f'"{item.name}" 구매 완료! ₩{credits_gained:,} 크레딧이 추가됐어요.')

        elif item.item_type == 'inventory':
            # 인벤토리 아이템: 구매 기록 + 인벤토리에 추가
            user.save(update_fields=['points'])

            Purchase.objects.create(
                user=user,
                item=item,
                points_spent=item.price_points,
                credits_gained=0,
            )
            Inventory.objects.create(
                user=user,
                item_name=item.name,
                item_image=item.image.name if item.image else '',
            )
            messages.success(request, f'"{item.name}"을(를) 획득했어요! 인벤토리를 확인해보세요.')

        else:
            # 알 수 없는 타입 — 안전하게 포인트만 차감하지 않고 롤백
            messages.error(request, '알 수 없는 아이템 타입이에요.')
            return redirect('shop:shop')

    return redirect('shop:shop')


@login_required
@require_POST
def spend_credit(request):
    user = request.user

    try:
        amount = int(request.POST.get('amount', 0))
    except ValueError:
        messages.error(request, '금액을 올바르게 입력해주세요.')
        return redirect('shop:shop')

    memo = request.POST.get('memo', '').strip()
    category = request.POST.get('category', 'other')
    spent_at = request.POST.get('spent_at') or str(localdate())

    if amount <= 0:
        messages.error(request, '금액은 1원 이상이어야 해요.')
        return redirect('shop:shop')

    if user.credits < amount:
        messages.error(request, f'크레딧이 부족해요. (보유: ₩{user.credits:,})')
        return redirect('shop:shop')

    with transaction.atomic():
        user.credits -= amount
        user.save(update_fields=['credits'])

        CreditLog.objects.create(
            user=user,
            amount=amount,
            category=category,
            memo=memo,
            spent_at=spent_at,
        )

    messages.success(request, f'₩{amount:,} 크레딧을 차감했어요.')
    return redirect('shop:shop')


@staff_member_required
@require_POST
def add_item(request):
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    item_type = request.POST.get('item_type', 'credit')
    price_points = request.POST.get('price_points', '').strip()
    credit_amount = request.POST.get('credit_amount', '').strip()
    image = request.FILES.get('image')

    # 필수 항목 검사
    if not name or not price_points:
        messages.error(request, '아이템 이름과 필요 포인트는 필수예요.')
        return redirect('shop:shop')

    # 크레딧권인데 금액이 없으면 경고
    if item_type == 'credit' and not credit_amount:
        messages.error(request, '크레딧권은 크레딧 금액을 입력해야 해요.')
        return redirect('shop:shop')

    # 이미지 타입 검사
    if image and image.content_type not in ALLOWED_IMAGE_TYPES:
        messages.error(request, 'PNG, WebP, GIF, JPEG 형식만 업로드할 수 있어요.')
        return redirect('shop:shop')

    ShopItem.objects.create(
        name=name,
        description=description,
        item_type=item_type,
        price_points=int(price_points),
        credit_amount=int(credit_amount) if credit_amount else None,
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