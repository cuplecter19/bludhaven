import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class SparkTag(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=30, unique=True)
    name_ko = models.CharField(max_length=50)
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return self.name_ko


class Note(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='atelier_notes',
    )
    title = models.CharField(max_length=200, blank=True, null=True)
    body = models.TextField()
    tag = models.ForeignKey(
        SparkTag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes',
    )
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-created_at'], name='atelier_note_timeline_idx'),
            models.Index(fields=['user', 'is_pinned'], name='atelier_note_pinned_idx'),
        ]

    def __str__(self):
        return self.title if self.title else self.body[:50]


class NoteReference(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='outgoing_refs')
    to_note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='incoming_refs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('from_note', 'to_note')]
        indexes = [
            models.Index(fields=['from_note'], name='atelier_ref_from_idx'),
            models.Index(fields=['to_note'], name='atelier_ref_to_idx'),
        ]

    def __str__(self):
        return f'{self.from_note_id} → {self.to_note_id}'


class MoodLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mood_logs',
    )
    mood_score = models.SmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    energy_score = models.SmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    emotion_tags = models.CharField(max_length=200, blank=True)
    behavior_tags = models.CharField(max_length=200, blank=True, default='')
    note = models.TextField(null=True, blank=True)
    logged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-logged_at'], name='atelier_mood_user_idx'),
        ]

    def __str__(self):
        return f'{self.user} mood={self.mood_score} at {self.logged_at}'


class PHQ9Log(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phq9_logs',
    )
    q1 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q2 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q3 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q4 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q5 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q6 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q7 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q8 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    q9 = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    total_score = models.SmallIntegerField()
    note = models.TextField(null=True, blank=True)
    logged_at = models.DateField(default=datetime.date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-logged_at'], name='atelier_phq9_user_idx'),
        ]

    def __str__(self):
        return f'{self.user} PHQ9={self.total_score} on {self.logged_at}'


class Project(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('done', 'Done'),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='atelier_projects',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    goal_description = models.TextField(blank=True, default='')
    completed_notes = models.TextField(null=True, blank=True)
    color_hex = models.CharField(max_length=7, default='#c8a96e')
    sort_order = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status'], name='atelier_proj_status_idx'),
            models.Index(fields=['user', 'sort_order'], name='atelier_proj_order_idx'),
        ]

    def __str__(self):
        return self.title


class ProjectNote(models.Model):
    id = models.BigAutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='project_notes')
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='project_links')
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('project', 'note')]

    def __str__(self):
        return f'{self.project} ↔ {self.note}'


class GoalLog(models.Model):
    LOG_TYPE_CHOICES = [
        ('note', 'Note'),
        ('done', 'Done'),
        ('next', 'Next'),
    ]

    id = models.BigAutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='goal_logs')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='goal_logs',
    )
    body = models.TextField()
    is_done = models.BooleanField(default=False)
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, default='note')
    logged_at = models.DateField(default=datetime.date.today)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', '-logged_at'], name='atelier_glog_proj_idx'),
            models.Index(fields=['user', '-logged_at'], name='atelier_glog_user_idx'),
        ]

    def __str__(self):
        return f'{self.project} log at {self.logged_at}'
