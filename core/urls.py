from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('mainpage/scene/active', views.active_scene, name='active_scene'),
    path('editor/scenes', views.editor_scene_list, name='editor_scene_list'),
    path('editor/scenes/create', views.create_scene, name='create_scene'),
    path('editor/scenes/<int:scene_id>', views.patch_scene, name='patch_scene'),

    path('editor/layers', views.create_layer, name='create_layer'),
    path('editor/layers/<int:layer_id>', views.patch_layer, name='patch_layer'),
    path('editor/layers/<int:layer_id>/delete', views.delete_layer, name='delete_layer'),
    path('editor/layers/reorder', views.reorder_layers, name='reorder_layers'),

    path('assets/upload', views.upload_asset, name='upload_asset'),

    path('editor/revisions', views.create_revision, name='create_revision'),
    path('editor/revisions/<int:revision_id>/restore', views.restore_revision, name='restore_revision'),
]
