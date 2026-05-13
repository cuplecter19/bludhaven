from django.db import models


class IndexImage(models.Model):
    LAYER_BACKGROUND = 'background'
    LAYER_MAIN = 'main'
    LAYER_STICKER = 'sticker'
    LAYER_CHOICES = [
        (LAYER_BACKGROUND, 'Background (Parallax)'),
        (LAYER_MAIN, 'Main'),
        (LAYER_STICKER, 'Sticker'),
    ]

    title     = models.CharField(max_length=100, blank=True)
    image     = models.ImageField(upload_to='core/images/')
    layer     = models.CharField(max_length=20, choices=LAYER_CHOICES, default=LAYER_MAIN)
    order     = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # 스티커 전용 배치 필드 (다른 layer에서는 무시됨)
    pos_left  = models.CharField(max_length=20, default='50%')
    pos_top   = models.CharField(max_length=20, default='50%')
    width     = models.CharField(max_length=20, default='160px')
    height    = models.CharField(max_length=20, default='auto')
    rotate    = models.IntegerField(default=0)
    z_index   = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ['layer', 'order', 'z_index']

    def __str__(self):
        return f"[{self.get_layer_display()}] {self.title or self.image.name} (#{self.order})"

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = IndexImage.objects.get(pk=self.pk)
                if old.image != self.image:
                    self._convert_image()
            except IndexImage.DoesNotExist:
                pass  # 신규 저장으로 처리됨 (pk가 지정되어 있어도 아직 DB에 없는 경우)
        else:
            self._convert_image()
        super().save(*args, **kwargs)

    def _convert_image(self):
        from .utils import convert_to_webp
        if self.image and not str(self.image.name).endswith('.webp'):
            webp_file = convert_to_webp(self.image)
            self.image.save(webp_file.name, webp_file, save=False)


class TextBlock(models.Model):
    POSITION_BG = 'bg_text'
    POSITION_BLOCK1 = 'block1'
    POSITION_BLOCK2 = 'block2'
    POSITION_BLOCK3 = 'block3'
    POSITION_CHOICES = [
        (POSITION_BG, 'Background Text'),
        (POSITION_BLOCK1, 'Text Block 1'),
        (POSITION_BLOCK2, 'Text Block 2'),
        (POSITION_BLOCK3, 'Text Block 3'),
    ]

    position  = models.CharField(max_length=20, choices=POSITION_CHOICES, default=POSITION_BLOCK1)
    content   = models.TextField()
    is_active = models.BooleanField(default=True)

    # 신규: 절대 좌표 배치
    pos_left  = models.CharField(max_length=20, default='5%')
    pos_top   = models.CharField(max_length=20, default='5%')
    font_size = models.CharField(max_length=20, default='1rem')
    color     = models.CharField(max_length=20, default='#ffffff')
    z_index   = models.PositiveIntegerField(default=20)

    def __str__(self):
        return self.get_position_display()


class ParallaxConfig(models.Model):
    """패럴랙스 배경 이미지 레이어별 설정값 (단일 레코드 운용)"""
    speed           = models.FloatField(default=0.4)
    blur_px         = models.IntegerField(default=0)
    overlay_opacity = models.FloatField(default=0.3)

    class Meta:
        verbose_name = 'Parallax Config'

    def __str__(self):
        return f'ParallaxConfig (speed={self.speed})'


class ClockWidgetConfig(models.Model):
    """시계 위젯 위치/스타일 설정 (단일 레코드)"""
    is_active = models.BooleanField(default=True)
    pos_left  = models.CharField(max_length=20, default='2%')
    pos_top   = models.CharField(max_length=20, default='2%')
    font_size = models.CharField(max_length=20, default='1rem')
    color     = models.CharField(max_length=20, default='#ffffff')
    z_index   = models.PositiveIntegerField(default=30)

    class Meta:
        verbose_name = 'Clock Widget Config'

    def __str__(self):
        return f'ClockWidgetConfig (active={self.is_active})'
