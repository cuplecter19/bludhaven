from django.contrib import admin

from .models import EditorRevision, MediaAsset, PageScene, SceneLayer


@admin.register(PageScene)
class PageSceneAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'viewport_mode', 'updated_at')
    list_filter = ('is_active', 'viewport_mode')
    search_fields = ('name',)


@admin.register(SceneLayer)
class SceneLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'scene', 'layer_type', 'layer_tier', 'z_index', 'enabled', 'updated_at')
    list_filter = ('layer_type', 'layer_tier', 'enabled')
    search_fields = ('scene__name',)


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'mime_type', 'storage_path', 'width', 'height', 'bytes', 'created_at')
    list_filter = ('kind', 'mime_type')
    search_fields = ('storage_path', 'hash_sha256')


@admin.register(EditorRevision)
class EditorRevisionAdmin(admin.ModelAdmin):
    list_display = ('id', 'scene', 'author', 'created_at')
    list_filter = ('scene',)
