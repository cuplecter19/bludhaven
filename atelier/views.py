import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import MoodLog, Note, NoteReference, PHQ9Log, SparkTag
from .services import (
    calculate_phq9_total,
    get_mood_trend,
    get_pulse_calendar_data,
    search_notes,
    sync_references,
)

EMOTION_TAGS = ['불안', '무기력', '예민', '슬픔', '피곤함', '괜찮음', '평온함', '좋음', '설렘']


def _note_to_dict(note, preview_len=80):
    return {
        'id': note.id,
        'title': note.title or '',
        'body_preview': note.body[:preview_len],  # safe: Python slicing handles short strings
        'tag': {'id': note.tag.id, 'name': note.tag.name, 'name_ko': note.tag.name_ko} if note.tag else None,
        'is_pinned': note.is_pinned,
        'created_at': note.created_at.isoformat(),
        'updated_at': note.updated_at.isoformat(),
        'ref_count': note.incoming_refs.count(),
    }


# ---------------------------------------------------------------------------
# Page views
# ---------------------------------------------------------------------------

@login_required
def home(request):
    notes = Note.objects.filter(user=request.user).order_by('-created_at')[:5]
    today = timezone.now().date()
    today_mood = MoodLog.objects.filter(
        user=request.user,
        logged_at__date=today,
    ).first()
    return render(request, 'atelier/home.html', {
        'notes': notes,
        'today_mood': today_mood,
    })


@login_required
def spark_list(request):
    notes = Note.objects.filter(user=request.user).order_by('-is_pinned', '-created_at')
    return render(request, 'atelier/spark/list.html', {'notes': notes})


@login_required
def spark_new(request):
    tags = SparkTag.objects.all()
    return render(request, 'atelier/spark/new.html', {'tags': tags})


@login_required
def spark_detail(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    tags = SparkTag.objects.all()
    return render(request, 'atelier/spark/detail.html', {'note': note, 'tags': tags})


@login_required
def pulse_home(request):
    return render(request, 'atelier/pulse/home.html')


@login_required
def pulse_checkin(request):
    return render(request, 'atelier/pulse/checkin.html', {'emotion_tags': EMOTION_TAGS})


PHQ9_QUESTIONS = [
    '기분이 가라앉거나 우울했다',
    '어떤 일에도 흥미나 즐거움을 거의 느끼지 못했다',
    '잠들기 어렵거나 너무 많이 잠을 잔다',
    '피곤하거나 에너지가 거의 없다',
    '식욕이 없거나 너무 많이 먹는다',
    '자신이 실패자라고 느꼈다',
    '집중하기 어렵다',
    '너무 느리게 움직이거나 반대로 너무 들떴다',
    '스스로를 해칠 생각이 들었다',
]


@login_required
def pulse_phq9(request):
    return render(request, 'atelier/pulse/phq9.html', {'phq9_questions': PHQ9_QUESTIONS})


# ---------------------------------------------------------------------------
# API views
# ---------------------------------------------------------------------------

@login_required
def api_notes_list(request):
    if request.method == 'GET':
        tag_name = request.GET.get('tag', '')
        try:
            page = max(1, int(request.GET.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            limit = min(50, max(1, int(request.GET.get('limit', 20))))
        except (ValueError, TypeError):
            limit = 20

        qs = Note.objects.filter(user=request.user).select_related('tag')
        if tag_name:
            qs = qs.filter(tag__name=tag_name)
        qs = qs.order_by('-is_pinned', '-created_at')

        count = qs.count()
        offset = (page - 1) * limit
        notes = qs[offset:offset + limit]
        return JsonResponse({'count': count, 'notes': [_note_to_dict(n) for n in notes]})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        body = data.get('body', '').strip()
        if not body:
            return JsonResponse({'error': 'body is required'}, status=400)

        tag = None
        tag_id = data.get('tag_id')
        if tag_id:
            try:
                tag = SparkTag.objects.get(id=tag_id)
            except SparkTag.DoesNotExist:
                pass

        note = Note.objects.create(
            user=request.user,
            title=data.get('title') or None,
            body=body,
            tag=tag,
            is_pinned=bool(data.get('is_pinned', False)),
        )
        sync_references(note)
        return JsonResponse(_note_to_dict(note), status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_notes_search(request):
    query = request.GET.get('q', '')
    notes = search_notes(request.user, query)
    return JsonResponse({'notes': [_note_to_dict(n) for n in notes[:50]]})


@login_required
def api_note_detail(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)

    if request.method == 'GET':
        d = _note_to_dict(note)
        d['body'] = note.body
        return JsonResponse(d)

    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'title' in data:
            note.title = data['title'] or None
        if 'body' in data:
            note.body = data['body']
        if 'is_pinned' in data:
            note.is_pinned = bool(data['is_pinned'])
        if 'tag_id' in data:
            tag_id = data['tag_id']
            if tag_id is None:
                note.tag = None
            else:
                try:
                    note.tag = SparkTag.objects.get(id=tag_id)
                except SparkTag.DoesNotExist:
                    pass
        note.save()
        sync_references(note)
        d = _note_to_dict(note)
        d['body'] = note.body
        return JsonResponse(d)

    elif request.method == 'DELETE':
        note.delete()
        return JsonResponse({}, status=204)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_note_references(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    outgoing = [
        {'id': ref.to_note.id, 'title': ref.to_note.title or '', 'body_preview': ref.to_note.body[:80]}
        for ref in note.outgoing_refs.select_related('to_note').all()
    ]
    incoming = [
        {'id': ref.from_note.id, 'title': ref.from_note.title or '', 'body_preview': ref.from_note.body[:80]}
        for ref in note.incoming_refs.select_related('from_note').all()
    ]
    return JsonResponse({'outgoing': outgoing, 'incoming': incoming})


@login_required
def api_mood_list(request):
    if request.method == 'GET':
        logs = MoodLog.objects.filter(user=request.user).order_by('-logged_at')[:30]
        data = [
            {
                'id': log.id,
                'mood_score': log.mood_score,
                'energy_score': log.energy_score,
                'emotion_tags': log.emotion_tags,
                'note': log.note,
                'logged_at': log.logged_at.isoformat(),
            }
            for log in logs
        ]
        return JsonResponse({'logs': data})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        try:
            mood_score = int(data['mood_score'])
        except (KeyError, ValueError, TypeError):
            return JsonResponse({'error': 'mood_score required'}, status=400)

        energy_score = data.get('energy_score')
        if energy_score is not None:
            try:
                energy_score = int(energy_score)
            except (ValueError, TypeError):
                energy_score = None

        log = MoodLog.objects.create(
            user=request.user,
            mood_score=mood_score,
            energy_score=energy_score,
            emotion_tags=data.get('emotion_tags', ''),
            note=data.get('note') or None,
        )
        return JsonResponse({
            'id': log.id,
            'mood_score': log.mood_score,
            'energy_score': log.energy_score,
            'emotion_tags': log.emotion_tags,
            'note': log.note,
            'logged_at': log.logged_at.isoformat(),
        }, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_mood_detail(request, log_id):
    log = get_object_or_404(MoodLog, id=log_id, user=request.user)
    return JsonResponse({
        'id': log.id,
        'mood_score': log.mood_score,
        'energy_score': log.energy_score,
        'emotion_tags': log.emotion_tags,
        'note': log.note,
        'logged_at': log.logged_at.isoformat(),
    })


@login_required
def api_phq9_list(request):
    if request.method == 'GET':
        logs = PHQ9Log.objects.filter(user=request.user).order_by('-logged_at')[:20]
        data = [
            {
                'id': log.id,
                'total_score': log.total_score,
                'logged_at': str(log.logged_at),
                'created_at': log.created_at.isoformat(),
            }
            for log in logs
        ]
        return JsonResponse({'logs': data})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        try:
            q_vals = [int(data[f'q{i}']) for i in range(1, 10)]
        except (KeyError, ValueError, TypeError):
            return JsonResponse({'error': 'q1 through q9 required'}, status=400)

        total = calculate_phq9_total(*q_vals)
        log = PHQ9Log.objects.create(
            user=request.user,
            q1=q_vals[0], q2=q_vals[1], q3=q_vals[2],
            q4=q_vals[3], q5=q_vals[4], q6=q_vals[5],
            q7=q_vals[6], q8=q_vals[7], q9=q_vals[8],
            total_score=total,
            note=data.get('note') or None,
        )
        return JsonResponse({
            'id': log.id,
            'total_score': log.total_score,
            'logged_at': str(log.logged_at),
            'show_crisis_info': log.q9 >= 1,
        }, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_pulse_calendar(request):
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid year/month'}, status=400)
    days = get_pulse_calendar_data(request.user, year, month)
    return JsonResponse({'year': year, 'month': month, 'days': days})


@login_required
def api_pulse_trend(request):
    try:
        days = int(request.GET.get('days', 30))
    except (ValueError, TypeError):
        days = 30
    data = get_mood_trend(request.user, days)
    return JsonResponse({'data': data})
