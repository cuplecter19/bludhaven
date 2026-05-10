from django.contrib import admin
from .models import (
    CompanionPreset,
    UserCompanion,
    DailyPlan,
    Task,
    TimerSession,
    DailySummary,
    RecurringTask,
)


@admin.register(CompanionPreset)
class CompanionPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'created_by')
    list_filter = ('is_default',)


@admin.register(UserCompanion)
class UserCompanionAdmin(admin.ModelAdmin):
    list_display = ('user', 'preset', 'affection_level')


@admin.register(DailyPlan)
class DailyPlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_date', 'status')
    list_filter = ('status',)
    date_hierarchy = 'plan_date'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'daily_plan', 'planned_start', 'planned_duration', 'actual_duration', 'status')
    list_filter = ('status',)


@admin.register(TimerSession)
class TimerSessionAdmin(admin.ModelAdmin):
    list_display = ('task', 'session_type', 'started_at', 'ended_at')
    list_filter = ('session_type',)


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('daily_plan', 'total_focus_minutes', 'completed_tasks', 'created_at')


@admin.register(RecurringTask)
class RecurringTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'recurrence_rule', 'planned_duration', 'is_active')
    list_filter = ('is_active',)
