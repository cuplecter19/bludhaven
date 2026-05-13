from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PageScene(models.Model):
    VIEWPORT_DESKTOP = 'desktop'
    VIEWPORT_MOBILE = 'mobile'
    VIEWPORT_BOTH = 'both'
    VIEWPORT_CHOICES = [
        (VIEWPORT_DESKTOP, 'Desktop'),
        (VIEWPORT_MOBILE, 'Mobile'),
        (VIEWPORT_BOTH, 'Both'),
    ]

    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=False)
    viewport_mode = models.CharField(max_length=20, choices=VIEWPORT_CHOICES, default=VIEWPORT_BOTH)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'id']

    def __str__(self):
        return self.name


class MediaAsset(models.Model):
    KIND_CHOICES = [
        ('background', 'Background'),
        ('main', 'Main'),
        ('parallax', 'Parallax'),
        ('sticker', 'Sticker'),
        ('generic', 'Generic'),
    ]

    kind = models.CharField(max_length=30, choices=KIND_CHOICES, default='generic')
    mime_type = models.CharField(max_length=100)
    storage_path = models.CharField(max_length=400)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    bytes = models.BigIntegerField()
    hash_sha256 = models.CharField(max_length=64)
    original_deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.kind}:{self.storage_path}'


class SceneLayer(models.Model):
    TYPE_BG_IMAGE = 'bg_image'
    TYPE_PARALLAX_FAR = 'parallax_far'
    TYPE_BG_TEXT = 'bg_text'
    TYPE_MAIN_IMAGE = 'main_image'
    TYPE_TEXT = 'text'
    TYPE_CLOCK = 'clock'
    TYPE_MENU_BUTTON = 'menu_button'
    TYPE_STICKER = 'sticker'
    TYPE_PARALLAX_NEAR = 'parallax_near'
    TYPE_PARALLAX_ULTRA_NEAR = 'parallax_ultra_near'

    LAYER_TYPE_CHOICES = [
        (TYPE_BG_IMAGE, 'Background Image'),
        (TYPE_PARALLAX_FAR, 'Parallax Far'),
        (TYPE_BG_TEXT, 'Background Text'),
        (TYPE_MAIN_IMAGE, 'Main Image'),
        (TYPE_TEXT, 'Text'),
        (TYPE_CLOCK, 'Clock'),
        (TYPE_MENU_BUTTON, 'Menu Button'),
        (TYPE_STICKER, 'Sticker'),
        (TYPE_PARALLAX_NEAR, 'Parallax Near'),
        (TYPE_PARALLAX_ULTRA_NEAR, 'Parallax Ultra Near'),
    ]

    TYPE_TIER_MAP = {
        TYPE_BG_IMAGE: -3,
        TYPE_PARALLAX_FAR: -2,
        TYPE_BG_TEXT: -1,
        TYPE_MAIN_IMAGE: 0,
        TYPE_TEXT: 1,
        TYPE_CLOCK: 1,
        TYPE_MENU_BUTTON: 1,
        TYPE_STICKER: 2,
        TYPE_PARALLAX_NEAR: 3,
        TYPE_PARALLAX_ULTRA_NEAR: 4,
    }

    scene = models.ForeignKey(PageScene, on_delete=models.CASCADE, related_name='layers')
    layer_type = models.CharField(max_length=40, choices=LAYER_TYPE_CHOICES)
    layer_tier = models.IntegerField(validators=[MinValueValidator(-3), MaxValueValidator(4)])
    z_index = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    x = models.FloatField(default=0, validators=[MinValueValidator(0.0)])
    y = models.FloatField(default=0, validators=[MinValueValidator(0.0)])
    width = models.FloatField(default=200, validators=[MinValueValidator(0.0)])
    height = models.FloatField(default=200, validators=[MinValueValidator(0.0)])

    rotation_deg = models.FloatField(default=0)
    scale = models.FloatField(default=1, validators=[MinValueValidator(0.01)])
    opacity = models.FloatField(default=1, validators=[MinValueValidator(0), MaxValueValidator(1)])

    settings_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['layer_tier', 'z_index', 'id']

    def clean(self):
        expected_tier = self.TYPE_TIER_MAP.get(self.layer_type)
        if expected_tier is None:
            raise ValidationError({'layer_type': 'unsupported layer_type'})
        if self.layer_tier != expected_tier:
            raise ValidationError({'layer_tier': f'layer_tier must be {expected_tier} for {self.layer_type}'})
        if self.layer_type == self.TYPE_STICKER and not (0 <= self.z_index <= 999):
            raise ValidationError({'z_index': 'sticker z_index must be in range 0..999'})

    def save(self, *args, **kwargs):
        self.layer_tier = self.TYPE_TIER_MAP[self.layer_type]
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.scene_id}:{self.layer_type}({self.z_index})'


class EditorRevision(models.Model):
    scene = models.ForeignKey(PageScene, on_delete=models.CASCADE, related_name='revisions')
    snapshot_json = models.JSONField(default=dict)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Revision#{self.pk} scene={self.scene_id}'
