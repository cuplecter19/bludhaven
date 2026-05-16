import csv
import io
import json
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate
from django.views.decorators.http import require_GET, require_POST

from .models import DailySummary, PhraseCard, ReviewLog, ScrambleAttempt, Tag
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


# ---------------------------------------------------------------------------
# CSV upload view
# ---------------------------------------------------------------------------

_BLANK_RE = re.compile(r'\[([^\]/]+)(?:/([^\]]*))?\]')

REQUIRED_COLUMNS = {'sentence_en', 'sentence_ko', 'phrase', 'phrase_ko', 'difficulty', 'tags'}


def _inject_hint(sentence_en, phrase, hint):
    """Embed hint into the blank markup: [phrase] -> [phrase/hint]."""
    if not hint:
        return sentence_en
    pattern = re.compile(r'\[' + re.escape(phrase) + r'(?:/[^\]]*)?\]')
    return pattern.sub(f'[{phrase}/{hint}]', sentence_en)


@login_required
def upload_csv(request):
    """POST /upload-csv/ — import PhraseCards from a CSV file."""
    if request.method != 'POST':
        return redirect('phrases:home')

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, 'CSV 파일을 선택해주세요.')
        return redirect('phrases:home')

    if not csv_file.name.lower().endswith('.csv'):
        messages.error(request, 'CSV 파일만 업로드할 수 있습니다.')
        return redirect('phrases:home')

    try:
        text = csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        messages.error(request, '파일 인코딩을 읽을 수 없습니다. UTF-8 CSV 파일을 업로드해주세요.')
        return redirect('phrases:home')

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        messages.error(request, 'CSV 파일이 비어 있습니다.')
        return redirect('phrases:home')

    missing = REQUIRED_COLUMNS - {f.strip() for f in reader.fieldnames}
    if missing:
        messages.error(request, f'필수 컬럼이 없습니다: {", ".join(sorted(missing))}')
        return redirect('phrases:home')

    created = 0
    errors = []
    for row_num, row in enumerate(reader, start=2):
        try:
            sentence_en = (row.get('sentence_en') or '').strip()
            sentence_ko = (row.get('sentence_ko') or '').strip()
            phrase = (row.get('phrase') or '').strip()
            phrase_ko = (row.get('phrase_ko') or '').strip()
            difficulty_raw = (row.get('difficulty') or '1').strip()
            tags_raw = (row.get('tags') or '').strip()
            hint = (row.get('hint') or '').strip()
            example_source = (row.get('example_source') or '').strip()
            memo = (row.get('memo') or '').strip()

            if not all([sentence_en, sentence_ko, phrase, phrase_ko]):
                errors.append(f'행 {row_num}: 필수 값이 비어 있습니다.')
                continue

            try:
                difficulty = int(difficulty_raw)
                if difficulty not in (1, 2, 3):
                    difficulty = 1
            except (ValueError, TypeError):
                difficulty = 1

            sentence_en = _inject_hint(sentence_en, phrase, hint)

            tag_slugs = [t.strip() for t in tags_raw.split(';') if t.strip()]
            tag_objects = []
            for slug in tag_slugs:
                tag, _ = Tag.objects.get_or_create(name=slug, defaults={'name_ko': slug})
                tag_objects.append(tag)

            card = PhraseCard.objects.create(
                user=request.user,
                sentence_en=sentence_en,
                sentence_ko=sentence_ko,
                phrase=phrase,
                phrase_ko=phrase_ko,
                difficulty=difficulty,
                example_source=example_source or None,
                memo=memo or None,
            )
            if tag_objects:
                card.tags.set(tag_objects)
            created += 1

        except Exception as exc:
            errors.append(f'행 {row_num}: {exc}')

    if created:
        messages.success(request, f'{created}개의 카드를 성공적으로 추가했습니다.')
    if errors:
        messages.error(request, '일부 행을 건너뜀: ' + ' / '.join(errors[:5]))

    return redirect('phrases:home')
