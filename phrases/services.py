from datetime import timedelta

from django.utils.timezone import localdate

from .models import DailySummary, PhraseCard, ReviewLog

# ---------------------------------------------------------------------------
# Leitner scheduling constants
# ---------------------------------------------------------------------------

BOX_INTERVALS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}


def _next_review_date(box_number, multiplier=1):
    return localdate() + timedelta(days=BOX_INTERVALS[box_number] * multiplier)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def get_due_cards(user, limit=20):
    """Return today's due cards ordered by box_number then next_review_at."""
    return list(
        PhraseCard.objects.filter(
            user=user,
            is_active=True,
            next_review_at__lte=localdate(),
        ).order_by('box_number', 'next_review_at')[:limit]
    )


def should_offer_scramble(card):
    """Return True when scramble mode should be offered after a cloze review."""
    return card.correct_streak >= 1


def update_daily_summary(user, mode, result):
    """Upsert today's DailySummary counters (called from process_review)."""
    summary, _ = DailySummary.objects.get_or_create(
        user=user,
        date=localdate(),
    )
    if mode == ReviewLog.MODE_CLOZE:
        summary.cloze_reviewed += 1
        if result in (ReviewLog.RESULT_GOOD, ReviewLog.RESULT_EASY):
            summary.cloze_correct += 1
    elif mode == ReviewLog.MODE_SCRAMBLE:
        summary.scramble_attempted += 1
        if result == ReviewLog.RESULT_GOOD:
            summary.scramble_correct += 1
    summary.save()
    return summary


POINTS_CLOZE_CORRECT = 100
POINTS_SCRAMBLE_CORRECT = 150


def process_review(card, result, mode, response_ms=None):
    """
    Process a review result for a PhraseCard.

    Applies the Leitner scheduling rules, creates a ReviewLog record and
    upserts the DailySummary.  Returns a dict containing the updated card
    state and whether to offer the scramble challenge.
    """
    box_before = card.box_number
    today = localdate()

    if result == ReviewLog.RESULT_AGAIN:
        card.box_number = 1
        card.next_review_at = today
        card.correct_streak = 0
    elif result == ReviewLog.RESULT_HARD:
        # box stays the same; interval stays the same
        card.next_review_at = _next_review_date(card.box_number)
        card.correct_streak = 0
    elif result == ReviewLog.RESULT_GOOD:
        card.box_number = min(card.box_number + 1, 5)
        card.next_review_at = _next_review_date(card.box_number)
        card.correct_streak += 1
    elif result == ReviewLog.RESULT_EASY:
        card.box_number = min(card.box_number + 1, 5)
        card.next_review_at = _next_review_date(card.box_number, multiplier=2)
        card.correct_streak += 1

    card.review_count += 1
    card.last_reviewed_at = today
    card.save()

    ReviewLog.objects.create(
        user=card.user,
        card=card,
        mode=mode,
        result=result,
        box_before=box_before,
        box_after=card.box_number,
        response_ms=response_ms,
    )

    update_daily_summary(card.user, mode, result)

    # Award points for correct answers
    points_earned = 0
    if result in (ReviewLog.RESULT_GOOD, ReviewLog.RESULT_EASY):
        if mode == ReviewLog.MODE_CLOZE:
            points_earned = POINTS_CLOZE_CORRECT
        elif mode == ReviewLog.MODE_SCRAMBLE:
            points_earned = POINTS_SCRAMBLE_CORRECT
    if points_earned:
        card.user.points += points_earned
        card.user.save(update_fields=['points'])

    return {
        'card_state': {
            'box_number': card.box_number,
            'next_review_at': str(card.next_review_at),
            'correct_streak': card.correct_streak,
            'review_count': card.review_count,
        },
        'offer_scramble': should_offer_scramble(card),
        'points_earned': points_earned,
    }
