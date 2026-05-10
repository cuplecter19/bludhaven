from django.urls import path
from . import views

app_name = 'scheduler'

urlpatterns = [
    # 페이지 뷰
    path('', views.page_today, name='today'),
    path('summary/<int:plan_id>/', views.page_summary, name='summary'),
    path('history/', views.page_history, name='history'),
    path('recurring/', views.page_recurring, name='recurring'),
    # API
    path('dialogue/', views.get_dialogue, name='get_dialogue'),
    path('plans/', views.create_today_plan, name='create_today_plan'),
    path('plans/today/', views.get_today_plan, name='get_today_plan'),
    path('plans/<int:plan_id>/summary/', views.get_summary, name='get_summary'),
    path('tasks/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/skip/', views.skip_task, name='skip_task'),
    path('timer/start/', views.start_timer, name='start_timer'),
    path('timer/stop/', views.stop_timer, name='stop_timer'),
    path('history/weekly/', views.weekly_history, name='weekly_history'),
    path('recurring-tasks/', views.recurring_tasks, name='recurring_tasks'),
    path('recurring-tasks/<int:task_id>/', views.delete_recurring_task, name='delete_recurring_task'),
    path('companion/presets/', views.companion_presets, name='companion_presets'),
    path('companion/presets/<int:preset_id>/', views.delete_companion_preset, name='delete_companion_preset'),
    path('companion/presets/<int:preset_id>/activate/', views.activate_companion_preset, name='activate_companion_preset'),
    path('companion/me/', views.get_active_companion, name='get_active_companion'),
]
