import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import GoalLog, MoodLog, Note, NoteReference, PHQ9Log, Project, ProjectNote, SparkTag
from .services import (
    calculate_phq9_total,
    get_behavior_tag_frequencies,
    get_goallog_dict,
    get_goal_logs_for_project,
    get_mood_trend,
    get_project_dict,
    get_projects_for_user,
    get_pulse_calendar_data,
    link_note_to_project,
    reorder_projects,
    search_notes,
    sync_references,
    unlink_note_from_project,
)

EMOTION_TAGS = ['불안', '무기력', '예민', '슬픔', '피곤함', '괜찮음', '평온함', '좋음', '설렘']

BEHAVIOR_TAGS = [
    {'text': '시작을 못 했다', 'slug': 'cant_start'},
    {'text': '중간에 그만뒀다', 'slug': 'gave_up'},
    {'text': '집중이 흩어졌다', 'slug': 'scattered'},
    {'text': '감정이 격해졌다', 'slug': 'emotional'},
    {'text': '몸이 너무 무거웠다', 'slug': 'exhausted'},
    {'text': '계획대로 됐다', 'slug': 'on_track'},
    {'text': '예상보다 잘 됐다', 'slug': 'better_than_expected'},
    {'text': '특별한 패턴 없음', 'slug': 'no_pattern'},
]

VALID_BEHAVIOR_SLUGS = {tag['slug'] for tag in BEHAVIOR_TAGS}

BEHAVIOR_SLUG_TO_TEXT = {tag['slug']: tag['text'] for tag in BEHAVIOR_TAGS}


def _note_to_dict(note, preview_len=80):
    return {
        'id': note.id,
        'title': note.title or '',
        'body_preview': note.body[:preview_len],  # safe: Python slicing is no-op when len < preview_len
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
    log_count = MoodLog.objects.filter(user=request.user).count()
    show_patterns = log_count >= 14
    pattern_frequencies = []
    if show_patterns:
        raw = get_behavior_tag_frequencies(request.user, days=30)
        if raw:
            max_count = raw[0]['count']
            for item in raw:
                pattern_frequencies.append({
                    'slug': item['slug'],
                    'text': BEHAVIOR_SLUG_TO_TEXT.get(item['slug'], item['slug']),
                    'count': item['count'],
                    'pct': round(item['count'] / max_count * 100) if max_count else 0,
                })
    return render(request, 'atelier/pulse/home.html', {
        'show_patterns': show_patterns and bool(pattern_frequencies),
        'pattern_frequencies': pattern_frequencies,
    })


@login_required
def pulse_checkin(request):
    return render(request, 'atelier/pulse/checkin.html', {
        'emotion_tags': EMOTION_TAGS,
        'behavior_tags': BEHAVIOR_TAGS,
    })


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
                'behavior_tags': log.behavior_tags,
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

        raw_behavior = data.get('behavior_tags', '')
        if raw_behavior:
            slugs = [s.strip() for s in raw_behavior.split(';') if s.strip()]
            invalid = [s for s in slugs if s not in VALID_BEHAVIOR_SLUGS]
            if invalid:
                return JsonResponse({'error': f'Invalid behavior slugs: {invalid}'}, status=400)
            behavior_tags = ';'.join(slugs)
        else:
            behavior_tags = ''

        log = MoodLog.objects.create(
            user=request.user,
            mood_score=mood_score,
            energy_score=energy_score,
            emotion_tags=data.get('emotion_tags', ''),
            behavior_tags=behavior_tags,
            note=data.get('note') or None,
        )
        return JsonResponse({
            'id': log.id,
            'mood_score': log.mood_score,
            'energy_score': log.energy_score,
            'emotion_tags': log.emotion_tags,
            'behavior_tags': log.behavior_tags,
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
        'behavior_tags': log.behavior_tags,
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


@login_required
def api_phq9_trend(request):
    """Return up to last 20 PHQ-9 scores in chronological order for trend chart."""
    logs = (
        PHQ9Log.objects
        .filter(user=request.user)
        .order_by('logged_at', 'created_at')
        .values('logged_at', 'created_at', 'total_score')[:20]
    )
    data = [{'logged_at': str(l['logged_at']), 'total_score': l['total_score']} for l in logs]
    return JsonResponse({'data': data})


@login_required
def spark_export(request, note_id):
    """Download a single note as a .md file."""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    lines = []
    if note.title:
        lines.append(f'# {note.title}\n\n')
    lines.append(note.body)
    content = ''.join(lines)
    safe_title = (note.title or f'note-{note.id}').replace('/', '-').replace('\\', '-')
    filename = f'{safe_title}.md'
    response = HttpResponse(content, content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Studio page views
# ---------------------------------------------------------------------------

# Colour palette offered on the project creation form — Pantone Colour of the Year references + extras
PROJECT_COLORS = [
    '#FFBE98',  # Peach Fuzz (2024)
    '#BB2649',  # Viva Magenta (2023)
    '#6667AB',  # Very Peri (2022)
    '#FF6F61',  # Living Coral (2019)
    '#88B04B',  # Greenery (2017)
    '#AD5E99',  # Radiant Orchid (2014)
    '#5BB8E8',  # 맑은 파란색 (Clear Sky Blue)
    '#B0B8C1',  # 연한 회색 (Soft Gray)
    '#E8C547',  # Warm Amber/Gold
    '#4ECDC4',  # Teal
    '#2C5F8A',  # Deep Navy
    '#8BC4A0',  # Sage Green
    '#F4A7B9',  # Soft Pink
    '#C8956C',  # Warm Terracotta
]


@login_required
def studio_home(request):
    status_filter = request.GET.get('status', 'active')
    projects = get_projects_for_user(request.user, status=status_filter)
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    for project in projects:
        active_logs = project.goal_logs.filter(is_deleted=False)
        project.weekly_log_count = active_logs.filter(logged_at__gte=week_start).count()
        project.done_log_count = active_logs.filter(is_done=True).count()
        last_log = active_logs.order_by('-logged_at', '-created_at').first()
        project.last_log_preview = last_log.body[:60] if last_log else ''
    return render(request, 'atelier/studio/home.html', {
        'projects': projects,
        'status_filter': status_filter,
    })


@login_required
def studio_new(request):
    return render(request, 'atelier/studio/new.html', {
        'colors': PROJECT_COLORS,
        'default_color': PROJECT_COLORS[0],
    })


@login_required
def studio_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    linked_notes = (
        Note.objects
        .filter(project_links__project=project)
        .order_by('-created_at')
    )
    goal_logs = get_goal_logs_for_project(project)
    project_statuses = [
        ('active', '진행 중'),
        ('paused', '잠시 멈춤'),
        ('done', '완료'),
    ]
    log_type_choices = [
        ('note', '메모'),
        ('done', '한 것'),
        ('next', '다음에 할 것'),
    ]
    active_logs = [log for log in goal_logs if not log.is_done]
    done_logs = [log for log in goal_logs if log.is_done]
    return render(request, 'atelier/studio/detail.html', {
        'project': project,
        'linked_notes': linked_notes,
        'goal_logs': goal_logs,
        'active_logs': active_logs,
        'done_logs': done_logs,
        'colors': PROJECT_COLORS,
        'project_statuses': project_statuses,
        'log_type_choices': log_type_choices,
    })


# ---------------------------------------------------------------------------
# Studio API views
# ---------------------------------------------------------------------------

@login_required
def api_projects_list(request):
    if request.method == 'GET':
        status_filter = request.GET.get('status', '')
        projects = get_projects_for_user(request.user, status=status_filter)
        return JsonResponse({'projects': [get_project_dict(p) for p in projects]})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        title = (data.get('title') or '').strip()
        if not title:
            return JsonResponse({'error': 'title is required'}, status=400)

        project = Project.objects.create(
            user=request.user,
            title=title,
            description=data.get('description') or None,
            color_hex=data.get('color_hex', '#c8a96e'),
            status=data.get('status', 'active'),
        )
        return JsonResponse(get_project_dict(project), status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'GET':
        return JsonResponse(get_project_dict(project))

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        updatable = ('title', 'description', 'status', 'goal_description',
                     'completed_notes', 'color_hex', 'sort_order')
        for field in updatable:
            if field in data:
                setattr(project, field, data[field])
        project.save()
        return JsonResponse(get_project_dict(project))

    if request.method == 'DELETE':
        project.delete()
        return JsonResponse({}, status=204)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_project_notes(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'GET':
        notes = Note.objects.filter(project_links__project=project).order_by('-created_at')
        return JsonResponse({'notes': [_note_to_dict(n) for n in notes]})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        note_id = data.get('note_id')
        if not note_id:
            return JsonResponse({'error': 'note_id is required'}, status=400)

        note = get_object_or_404(Note, id=note_id, user=request.user)
        created = link_note_to_project(project, note)
        status_code = 201 if created else 200
        return JsonResponse({'linked': True, 'note': _note_to_dict(note)}, status=status_code)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_project_note_unlink(request, project_id, note_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    project = get_object_or_404(Project, id=project_id, user=request.user)
    note = get_object_or_404(Note, id=note_id, user=request.user)
    unlink_note_from_project(project, note)
    return JsonResponse({}, status=204)


@login_required
def api_projects_reorder(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    ordered_ids = data.get('ordered_ids', [])
    if not isinstance(ordered_ids, list):
        return JsonResponse({'error': 'ordered_ids must be a list'}, status=400)

    reorder_projects(request.user, ordered_ids)
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# GoalLog API views
# ---------------------------------------------------------------------------

@login_required
def api_goal_logs_list(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'GET':
        logs = get_goal_logs_for_project(project)
        return JsonResponse({'logs': [get_goallog_dict(log) for log in logs]})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        body = (data.get('body') or '').strip()
        if not body:
            return JsonResponse({'error': 'body is required'}, status=400)

        log_type = data.get('log_type', 'note')
        if log_type not in {'note', 'done', 'next'}:
            log_type = 'note'

        log = GoalLog.objects.create(
            project=project,
            user=request.user,
            body=body,
            is_done=bool(data.get('is_done', False)),
            log_type=log_type,
        )
        return JsonResponse(get_goallog_dict(log), status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_goal_log_detail(request, project_id, log_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    log = get_object_or_404(GoalLog, id=log_id, project=project, user=request.user)

    if request.method == 'GET':
        return JsonResponse(get_goallog_dict(log))

    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'body' in data:
            body = (data['body'] or '').strip()
            if body:
                log.body = body
        if 'is_done' in data:
            log.is_done = bool(data['is_done'])
        if 'log_type' in data and data['log_type'] in {'note', 'done', 'next'}:
            log.log_type = data['log_type']
        if 'is_deleted' in data:
            log.is_deleted = bool(data['is_deleted'])
        log.save()
        return JsonResponse(get_goallog_dict(log))

    if request.method == 'DELETE':
        log.is_deleted = True
        log.save(update_fields=['is_deleted'])
        return JsonResponse({}, status=204)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
