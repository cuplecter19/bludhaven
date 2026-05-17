from django.db import models
from django.conf import settings


class ShopItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
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
    """포인트로 아이템을 구매한 지출 기록 — 영구 보존"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
    )
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT)
    points_spent = models.PositiveIntegerField()
    purchased_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.item.name} ({self.purchased_at:%Y-%m-%d})"


class Review(models.Model):
    """상점 구매 후기"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop_reviews',
    )
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='shop_reviews/',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.user}] {self.title}"


class ShopSetting(models.Model):
    """상점 전역 설정 (싱글톤)"""
    default_review_image = models.ImageField(
        upload_to='shop_settings/',
        null=True,
        blank=True,
        help_text="후기에 이미지가 없을 때 표시할 기본 이미지",
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Shop Settings'