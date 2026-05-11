from django.db import models


class IndexImage(models.Model):
    LAYER_BACKGROUND = 'background'
    LAYER_MAIN = 'main'
    LAYER_CHOICES = [
        (LAYER_BACKGROUND, 'Background'),
        (LAYER_MAIN, 'Main'),
    ]

    title = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='core/images/')
    layer = models.CharField(max_length=20, choices=LAYER_CHOICES, default=LAYER_MAIN)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['layer', 'order']

    def __str__(self):
        return f"[{self.get_layer_display()}] {self.title or self.image.name} (#{self.order})"


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

    position = models.CharField(max_length=20, choices=POSITION_CHOICES, unique=True)
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_position_display()
