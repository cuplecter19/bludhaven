from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    nickname = models.CharField(max_length=50, unique=True)

    REQUIRED_FIELDS = ['nickname', 'email']

    points = models.PositiveIntegerField(default=0)
    exp = models.PositiveIntegerField(default=0)
    streak_count = models.PositiveIntegerField(default=0)
    credits = models.PositiveIntegerField(default=0)

    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    theme_preference = models.CharField(max_length=20, default='default')

    def __str__(self):
        return self.nickname if self.nickname else self.username

class Inventory(models.Model):
    """유저가 보유 중인 인벤토리 아이템"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inventory',
    )
    # ShopItem을 직접 참조하지 않고 shop 앱에 의존하지 않도록
    # item 정보는 문자열로 스냅샷 저장 + FK 병행
    item_name = models.CharField(max_length=100, default='')   # 구매 시점 이름 스냅샷
    item_image = models.CharField(max_length=255, blank=True)  # 이미지 경로 스냅샷
    acquired_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)   # 소모성 아이템용
    memo = models.CharField(max_length=200, blank=True)
 
    def __str__(self):
        return f"[{self.user.nickname}] {self.item_name}"