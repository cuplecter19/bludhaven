from django.contrib import admin

from .models import DailySummary, PhraseCard, ReviewLog, ScrambleAttempt, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_ko', 'color_hex', 'created_at')
    search_fields = ('name', 'name_ko')


@admin.register(PhraseCard)
class PhraseCardAdmin(admin.ModelAdmin):
    list_display = ('phrase', 'user', 'box_number', 'next_review_at', 'difficulty', 'is_active')
    list_filter = ('box_number', 'difficulty', 'is_active')
    search_fields = ('phrase', 'sentence_en', 'phrase_ko')
    raw_id_fields = ('user', 'source_word')
    filter_horizontal = ('tags',)


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ('card', 'user', 'mode', 'result', 'box_before', 'box_after', 'reviewed_at')
    list_filter = ('mode', 'result')
    raw_id_fields = ('user', 'card')


@admin.register(ScrambleAttempt)
class ScrambleAttemptAdmin(admin.ModelAdmin):
    list_display = ('card', 'user', 'attempt_number', 'is_correct', 'attempted_at')
    list_filter = ('is_correct',)
    raw_id_fields = ('user', 'card')


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'cloze_reviewed', 'cloze_correct', 'scramble_attempted', 'scramble_correct')
    raw_id_fields = ('user',)
