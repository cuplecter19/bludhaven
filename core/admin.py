from django.contrib import admin
from .models import IndexImage, TextBlock


@admin.register(IndexImage)
class IndexImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'layer', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('layer', 'is_active')


@admin.register(TextBlock)
class TextBlockAdmin(admin.ModelAdmin):
    list_display = ('position', 'is_active')
    list_editable = ('is_active',)
