from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('api/sticker/<int:pk>/move/',   views.sticker_move,       name='sticker_move'),
    path('api/sticker/<int:pk>/update/', views.sticker_update,     name='sticker_update'),
    path('api/sticker/<int:pk>/delete/', views.sticker_delete,     name='sticker_delete'),
    path('api/sticker/add/',             views.sticker_add,        name='sticker_add'),
    path('api/textblock/<int:pk>/update/', views.textblock_update, name='textblock_update'),
    path('api/clock/update/',            views.clock_update,       name='clock_update'),
    path('api/parallax/update/',         views.parallax_update,    name='parallax_update'),
    path('api/state/',                   views.layout_state,       name='layout_state'),
]
