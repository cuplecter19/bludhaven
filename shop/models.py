from django.db import models
from django.conf import settings


class ShopItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('credit', '크레딧'),
        ('inventory', '아이템'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        default='credit',
    )
    price_points = models.PositiveIntegerField()
    credit_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="item_type이 'credit'일 때만 입력",
    )
    image = models.ImageField(
        upload_to='shop_items/',
        null=True,
        blank=True,
        help_text="PNG, WebP 권장",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Purchase(models.Model):
    """포인트로 아이템을 구매한 거래 기록 — 영구 보존"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
    )
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT)
    points_spent = models.PositiveIntegerField()
    credits_gained = models.PositiveIntegerField(default=0)
    purchased_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.item.name} ({self.purchased_at:%Y-%m-%d})"


class CreditLog(models.Model):
    """크레딧 사용(지출) 내역 — 사용자가 직접 기록"""
    CATEGORY_CHOICES = [
        ('game', '게임'),
        ('book', '책'),
        ('hobby', '취미'),
        ('other', '기타'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_logs',
    )
    amount = models.PositiveIntegerField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    memo = models.CharField(max_length=200, blank=True)
    spent_at = models.DateField()
    logged_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} -{self.amount}원 ({self.memo})"