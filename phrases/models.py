import re
import random

from django.conf import settings
from django.db import models
from django.utils.timezone import localdate


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    name_ko = models.CharField(max_length=100)
    color_hex = models.CharField(max_length=7, default='#c8a96e')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PhraseCard(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phrase_cards',
    )
    sentence_en = models.TextField()
    sentence_ko = models.TextField()
    phrase = models.CharField(max_length=150)
    phrase_ko = models.CharField(max_length=200)
    example_source = models.CharField(max_length=200, blank=True, null=True)
    difficulty = models.SmallIntegerField(default=1)
    box_number = models.SmallIntegerField(default=1)
    next_review_at = models.DateField(default=localdate)
    last_reviewed_at = models.DateField(blank=True, null=True)
    review_count = models.IntegerField(default=0)
    correct_streak = models.SmallIntegerField(default=0)
    source_word = models.ForeignKey(
        'leitner.WordSense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='phrase_cards',
    )
    is_active = models.BooleanField(default=True)
    memo = models.TextField(blank=True, null=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='phrase_cards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['user', 'next_review_at', 'box_number'],
                name='phrases_card_review_idx',
                condition=models.Q(is_active=True),
            ),
        ]

    def __str__(self):
        return f"[{self.user}] {self.phrase} (Box {self.box_number})"

    # ------------------------------------------------------------------
    # Blank markup helpers  –  [answer] or [answer/hint]
    # ------------------------------------------------------------------
    _BLANK_RE = re.compile(r'\[([^\]/]+)(?:/([^\]]*))?\]')

    def get_cloze_data(self):
        """Parse sentence_en markup and return segment list for cloze mode."""
        sentence = self.sentence_en
        segments = []
        last = 0
        for m in self._BLANK_RE.finditer(sentence):
            if m.start() > last:
                segments.append({'type': 'text', 'value': sentence[last:m.start()]})
            segments.append({
                'type': 'blank',
                'answer': m.group(1),
                'hint': m.group(2) or '',
            })
            last = m.end()
        if last < len(sentence):
            segments.append({'type': 'text', 'value': sentence[last:]})
        return {
            'segments': segments,
            'sentence_ko': self.sentence_ko,
            'phrase_ko': self.phrase_ko,
        }

    def get_display_sentence(self):
        """Return the complete sentence with markup removed."""
        return self._BLANK_RE.sub(lambda m: m.group(1), self.sentence_en)

    def get_scramble_words(self, seed=None):
        """Return shuffled words and the correct order for scramble mode."""
        words = self.get_display_sentence().split()
        correct_order = list(words)
        shuffled = list(words)
        random.Random(seed).shuffle(shuffled)
        return {
            'shuffled': shuffled,
            'correct_order': correct_order,
        }


class ReviewLog(models.Model):
    MODE_CLOZE = 'cloze'
    MODE_SCRAMBLE = 'scramble'
    MODE_CHOICES = [(MODE_CLOZE, 'Cloze'), (MODE_SCRAMBLE, 'Scramble')]

    RESULT_AGAIN = 'again'
    RESULT_HARD = 'hard'
    RESULT_GOOD = 'good'
    RESULT_EASY = 'easy'
    RESULT_CHOICES = [
        (RESULT_AGAIN, 'Again'),
        (RESULT_HARD, 'Hard'),
        (RESULT_GOOD, 'Good'),
        (RESULT_EASY, 'Easy'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phrase_review_logs',
    )
    card = models.ForeignKey(
        PhraseCard,
        on_delete=models.CASCADE,
        related_name='review_logs',
    )
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    box_before = models.SmallIntegerField()
    box_after = models.SmallIntegerField()
    response_ms = models.IntegerField(blank=True, null=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-reviewed_at'], name='phrases_rlog_user_idx'),
            models.Index(fields=['card', '-reviewed_at'], name='phrases_rlog_card_idx'),
        ]

    def __str__(self):
        return f"[{self.mode}:{self.result}] {self.card.phrase} ({self.box_before}→{self.box_after})"


class ScrambleAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='scramble_attempts',
    )
    card = models.ForeignKey(
        PhraseCard,
        on_delete=models.CASCADE,
        related_name='scramble_attempts',
    )
    submitted_order = models.TextField()
    correct_order = models.TextField()
    is_correct = models.BooleanField()
    attempt_number = models.SmallIntegerField()
    time_taken_ms = models.IntegerField(blank=True, null=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-attempted_at'], name='phrases_sattempt_idx'),
        ]

    def __str__(self):
        result = 'O' if self.is_correct else 'X'
        return f"[{result}] {self.card.phrase} attempt #{self.attempt_number}"


class DailySummary(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phrase_daily_summaries',
    )
    date = models.DateField()
    cloze_reviewed = models.IntegerField(default=0)
    cloze_correct = models.IntegerField(default=0)
    scramble_attempted = models.IntegerField(default=0)
    scramble_correct = models.IntegerField(default=0)
    new_cards_added = models.IntegerField(default=0)
    study_duration_sec = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        indexes = [
            models.Index(fields=['user', 'date'], name='phrases_dsummary_idx'),
        ]

    def __str__(self):
        return f"[{self.user}] {self.date}"
