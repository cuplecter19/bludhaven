from django.urls import path
from . import views

app_name = 'atelier'

urlpatterns = [
    # Page views
    path('', views.home, name='home'),
    path('spark/', views.spark_list, name='spark_list'),
    path('spark/new/', views.spark_new, name='spark_new'),
    path('spark/<int:note_id>/', views.spark_detail, name='spark_detail'),
    path('pulse/', views.pulse_home, name='pulse_home'),
    path('pulse/checkin/', views.pulse_checkin, name='pulse_checkin'),
    path('pulse/phq9/', views.pulse_phq9, name='pulse_phq9'),

    # Studio page views
    path('studio/', views.studio_home, name='studio_home'),
    path('studio/new/', views.studio_new, name='studio_new'),
    path('studio/<int:project_id>/', views.studio_detail, name='studio_detail'),

    # API endpoints — notes
    path('api/notes/', views.api_notes_list, name='api_notes_list'),
    path('api/notes/search/', views.api_notes_search, name='api_notes_search'),
    path('api/notes/<int:note_id>/', views.api_note_detail, name='api_note_detail'),
    path('api/notes/<int:note_id>/references/', views.api_note_references, name='api_note_references'),

    # API endpoints — mood / pulse
    path('api/mood/', views.api_mood_list, name='api_mood_list'),
    path('api/mood/<int:log_id>/', views.api_mood_detail, name='api_mood_detail'),
    path('api/phq9/', views.api_phq9_list, name='api_phq9_list'),
    path('api/pulse/calendar/', views.api_pulse_calendar, name='api_pulse_calendar'),
    path('api/pulse/trend/', views.api_pulse_trend, name='api_pulse_trend'),

    # API endpoints — projects (Studio)
    path('api/projects/', views.api_projects_list, name='api_projects_list'),
    path('api/projects/reorder/', views.api_projects_reorder, name='api_projects_reorder'),
    path('api/projects/<int:project_id>/', views.api_project_detail, name='api_project_detail'),
    path('api/projects/<int:project_id>/notes/', views.api_project_notes, name='api_project_notes'),
    path('api/projects/<int:project_id>/notes/<int:note_id>/', views.api_project_note_unlink, name='api_project_note_unlink'),
]
