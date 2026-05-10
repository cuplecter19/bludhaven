from django.db import models
from django.conf import settings


class CompanionPreset(models.Model):
    name = models.CharField(max_length=100)
    animal_emoji = models.CharField(max_length=10, blank=True)
    theme_color = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to='companion_images/', null=True, blank=True)
    dialogue_map = models.JSONField(default=dict)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companion_presets',
    )
    system_prompt = models.TextField(
        blank=True,
        default="You are a helpful and supportive companion that encourages the user to stay focused and achieve their goals. Provide positive reinforcement, gentle reminders, and celebrate their progress. Avoid being critical or negative, and always respond in a friendly and uplifting manner."
    )

    def __str__(self):
        return self.name


class UserCompanion(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='companion',
    )
    preset = models.ForeignKey(
        CompanionPreset,
        on_delete=models.PROTECT,
        related_name='companions',
    )
    affection_level = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user} - {self.preset}"


class DailyPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_plans',
    )
    plan_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        unique_together = ('user', 'plan_date')

    def __str__(self):
        return f"{self.user} {self.plan_date} ({self.status})"


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DONE = 'done', 'Done'
        SKIPPED = 'skipped', 'Skipped'

    daily_plan = models.ForeignKey(DailyPlan, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    planned_start = models.TimeField(null=True, blank=True)
    planned_duration = models.IntegerField(null=True, blank=True)
    actual_duration = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    point_reward = models.PositiveIntegerField(default=10)
    display_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.title} ({self.status})"


class TimerSession(models.Model):
    class SessionType(models.TextChoices):
        FOCUS = 'focus', 'Focus'
        BREAK = 'break', 'Break'

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='timer_sessions')
    session_type = models.CharField(max_length=10, choices=SessionType.choices)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.task} - {self.session_type}"


class DailySummary(models.Model):
    daily_plan = models.OneToOneField(DailyPlan, on_delete=models.CASCADE, related_name='summary')
    tasks_total = models.IntegerField(default=0)
    completed_tasks = models.IntegerField(default=0)
    points_earned = models.IntegerField(default=0)
    total_focus_minutes = models.IntegerField(default=0)
    break_minutes = models.IntegerField(default=0)
    adherence_pct = models.FloatField(default=0.0)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.daily_plan}"


class RecurringTask(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recurring_tasks',
    )
    title = models.CharField(max_length=200)
    recurrence_rule = models.CharField(max_length=100)
    planned_duration = models.IntegerField(null=True, blank=True)
    point_reward = models.PositiveIntegerField(default=10)
    preferred_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.recurrence_rule})"
