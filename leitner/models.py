from django.db import models, transaction
from django.conf import settings
from django.utils.timezone import localdate
from datetime import timedelta


class Word(models.Model):
    word = models.CharField(max_length=100, unique=True)
    pronunciation = models.CharField(max_length=100, blank=True)
    part_of_speech = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.word


class WordSense(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='senses')
    meaning = models.CharField(max_length=200)
    example_en = models.TextField(blank=True)
    example_ko = models.TextField(blank=True)
    context_tag = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.word.word} - {self.meaning}"


class UserCard(models.Model):
    REVIEW_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 999}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cards')
    sense = models.ForeignKey(WordSense, on_delete=models.CASCADE)

    box_number = models.IntegerField(default=1)
    next_review_at = models.DateField(default=localdate)

    correct_count = models.IntegerField(default=0)
    wrong_count = models.IntegerField(default=0)
    last_reviewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'sense')  # 중복 카드 방지

    def calculate_next_review(self, is_correct, response_ms=None):
        box_before = self.box_number

        if is_correct:
            self.box_number = min(self.box_number + 1, 5)
            self.correct_count += 1
        else:
            self.box_number = 1
            self.wrong_count += 1

        self.next_review_at = localdate() + timedelta(days=self.REVIEW_INTERVALS[self.box_number])

        with transaction.atomic():
            self.save()
            ReviewLog.objects.create(
                user=self.user,
                card=self,
                is_correct=is_correct,
                response_ms=response_ms,
                box_before=box_before,
                box_after=self.box_number,
            )

    def __str__(self):
        return f"[{self.user}] {self.sense.word.word} (Box {self.box_number})"


class ReviewLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    card = models.ForeignKey(UserCard, on_delete=models.CASCADE)

    is_correct = models.BooleanField()
    response_ms = models.IntegerField(null=True, blank=True)

    box_before = models.IntegerField()
    box_after = models.IntegerField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        result = "O" if self.is_correct else "X"
        return f"[{result}] {self.card.sense.word.word} ({self.box_before} → {self.box_after})"