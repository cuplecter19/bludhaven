from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    nickname = models.CharField(max_length=50, unique=True)

    REQUIRED_FIELDS = ['nickname', 'email']

    points = models.PositiveIntegerField(default=0)
    exp = models.PositiveIntegerField(default=0)
    streak_count = models.PositiveIntegerField(default=0)

    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    theme_preference = models.CharField(max_length=20, default='default')

    def __str__(self):
        return self.nickname if self.nickname else self.username