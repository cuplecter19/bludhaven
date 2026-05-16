from django.urls import path

from . import views

app_name = 'phrases'

urlpatterns = [
    # Page views
    path('', views.home, name='home'),
    path('cloze/', views.cloze_view, name='cloze'),
    path('scramble/', views.scramble_view, name='scramble'),
    path('stats/', views.stats_view, name='stats'),

    # API endpoints
    path('api/cards/due/', views.api_cards_due, name='api_cards_due'),
    path('api/cards/<int:card_id>/', views.api_card_detail, name='api_card_detail'),
    path('api/review/', views.api_review, name='api_review'),
    path('api/scramble/', views.api_scramble, name='api_scramble'),
    path('api/stats/', views.api_stats, name='api_stats'),
    # CSV upload
    path('upload-csv/', views.upload_csv, name='upload_csv'),
]
