from django.contrib import admin
from .models import SparkTag, Note, NoteReference, MoodLog, PHQ9Log, Project, ProjectNote


@admin.register(SparkTag)
class SparkTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_ko', 'sort_order')
    ordering = ('sort_order',)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'tag', 'is_pinned', 'created_at')
    list_filter = ('tag', 'is_pinned')
    search_fields = ('title', 'body')


@admin.register(NoteReference)
class NoteReferenceAdmin(admin.ModelAdmin):
    list_display = ('from_note', 'to_note', 'created_at')


@admin.register(MoodLog)
class MoodLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'mood_score', 'energy_score', 'emotion_tags', 'logged_at')
    list_filter = ('mood_score',)


@admin.register(PHQ9Log)
class PHQ9LogAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_score', 'logged_at', 'created_at')


admin.site.register(ProjectNote)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'status', 'sort_order', 'updated_at')
    list_filter = ('status',)
    search_fields = ('title',)
    ordering = ('user', 'sort_order')
