import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import localdate
from django.views.decorators.http import require_GET, require_POST

from .models import DailySummary, PhraseCard, ReviewLog, ScrambleAttempt
from .services import get_due_cards, process_review


# ---------------------------------------------------------------------------
# Page views
# ---------------------------------------------------------------------------

@login_required
def home(request):
    """Today's learning overview."""
    today = localdate()
    due_count = PhraseCard.objects.filter(
        user=request.user,
        is_active=True,
        next_review_at__lte=today,
    ).count()
    summary = DailySummary.objects.filter(user=request.user, date=today).first()
    return render(request, 'phrases/home.html', {
        'due_count': due_count,
        'summary': summary,
    })


@login_required
def cloze_view(request):
    return render(request, 'phrases/cloze.html')


@login_required
def scramble_view(request):
    return render(request, 'phrases/scramble.html')


@login_required
def stats_view(request):
    summaries = (
        DailySummary.objects
        .filter(user=request.user)
        .order_by('-date')[:30]
    )
    return render(request, 'phrases/stats.html', {'summaries': summaries})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _card_to_dict(card):
    return {
        'id': card.id,
        'phrase': card.phrase,
        'phrase_ko': card.phrase_ko,
        'box_number': card.box_number,
        'difficulty': card.difficulty,
        'cloze_data': card.get_cloze_data(),
        'scramble_data': card.get_scramble_words(),
        'tags': list(card.tags.values('id', 'name', 'name_ko', 'color_hex')),
    }


# ---------------------------------------------------------------------------
# API views
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_cards_due(request):
    """GET /api/cards/due/"""
    limit = int(request.GET.get('limit', 20))
    mode = request.GET.get('mode', 'cloze')
    cards = get_due_cards(request.user, limit=limit)
    return JsonResponse({
        'count': len(cards),
        'mode': mode,
        'cards': [_card_to_dict(c) for c in cards],
    })


@login_required
@require_GET
def api_card_detail(request, card_id):
    """GET /api/cards/<id>/"""
    card = get_object_or_404(PhraseCard, id=card_id, user=request.user)
    return JsonResponse(_card_to_dict(card))


@login_required
@require_POST
def api_review(request):
    """POST /api/review/  –  submit a cloze review result."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    card_id = data.get('card_id')
    result = data.get('result')
    response_ms = data.get('response_ms')

    valid_results = (
        ReviewLog.RESULT_AGAIN,
        ReviewLog.RESULT_HARD,
        ReviewLog.RESULT_GOOD,
        ReviewLog.RESULT_EASY,
    )
    if result not in valid_results:
        return JsonResponse({'error': 'Invalid result'}, status=400)

    try:
        card = PhraseCard.objects.get(id=card_id, user=request.user)
    except PhraseCard.DoesNotExist:
        return JsonResponse({'error': 'Card not found'}, status=404)

    outcome = process_review(
        card,
        result=result,
        mode=ReviewLog.MODE_CLOZE,
        response_ms=response_ms,
    )
    return JsonResponse(outcome)


@login_required
@require_POST
def api_scramble(request):
    """POST /api/scramble/  –  submit a scramble attempt."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    card_id = data.get('card_id')
    submitted_order = data.get('submitted_order', [])
    time_taken_ms = data.get('time_taken_ms')

    try:
        card = PhraseCard.objects.get(id=card_id, user=request.user)
    except PhraseCard.DoesNotExist:
        return JsonResponse({'error': 'Card not found'}, status=404)

    scramble_data = card.get_scramble_words()
    correct_order = scramble_data['correct_order']
    is_correct = submitted_order == correct_order

    prev_attempts = ScrambleAttempt.objects.filter(
        user=request.user,
        card=card,
    ).count()

    ScrambleAttempt.objects.create(
        user=request.user,
        card=card,
        submitted_order=json.dumps(submitted_order),
        correct_order=json.dumps(correct_order),
        is_correct=is_correct,
        attempt_number=prev_attempts + 1,
        time_taken_ms=time_taken_ms,
    )

    if is_correct:
        outcome = process_review(
            card,
            result=ReviewLog.RESULT_GOOD,
            mode=ReviewLog.MODE_SCRAMBLE,
            response_ms=time_taken_ms,
        )
    else:
        outcome = {
            'card_state': {
                'box_number': card.box_number,
                'next_review_at': str(card.next_review_at),
                'correct_streak': card.correct_streak,
                'review_count': card.review_count,
            },
            'offer_scramble': False,
        }

    outcome['is_correct'] = is_correct
    outcome['correct_order'] = correct_order
    return JsonResponse(outcome)


@login_required
@require_GET
def api_stats(request):
    """GET /api/stats/"""
    summaries = list(
        DailySummary.objects
        .filter(user=request.user)
        .order_by('-date')[:30]
        .values(
            'date',
            'cloze_reviewed',
            'cloze_correct',
            'scramble_attempted',
            'scramble_correct',
            'new_cards_added',
            'study_duration_sec',
        )
    )
    return JsonResponse({'summaries': summaries})
