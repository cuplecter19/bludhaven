from django.contrib import admin
from .models import IndexImage, TextBlock, ParallaxConfig, ClockWidgetConfig


@admin.register(IndexImage)
class IndexImageAdmin(admin.ModelAdmin):
    list_display  = ('title', 'layer', 'order', 'z_index', 'is_active')
    list_editable = ('order', 'z_index', 'is_active')
    list_filter   = ('layer', 'is_active')
    fieldsets = (
        (None, {'fields': ('title', 'image', 'layer', 'order', 'is_active')}),
        ('배치 (스티커 전용)', {
            'classes': ('collapse',),
            'fields': ('pos_left', 'pos_top', 'width', 'height', 'rotate', 'z_index'),
        }),
    )


@admin.register(TextBlock)
class TextBlockAdmin(admin.ModelAdmin):
    list_display  = ('position', 'is_active', 'pos_left', 'pos_top')
    list_editable = ('is_active',)
    fieldsets = (
        (None, {'fields': ('position', 'content', 'is_active')}),
        ('배치', {'fields': ('pos_left', 'pos_top', 'font_size', 'color', 'z_index')}),
    )


@admin.register(ParallaxConfig)
class ParallaxConfigAdmin(admin.ModelAdmin):
    list_display = ('speed', 'blur_px', 'overlay_opacity')


@admin.register(ClockWidgetConfig)
class ClockWidgetConfigAdmin(admin.ModelAdmin):
    list_display = ('is_active', 'pos_left', 'pos_top', 'font_size')
