import datetime

from django.db.models import Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from .utils import extract_references, is_numeric
from .models import GoalLog, MoodLog, Note, NoteReference, Project, ProjectNote


def sync_references(note: Note) -> None:
    """Parse note.body for [[ref]] patterns and update NoteReference table."""
    tokens = extract_references(note.body)
    resolved_ids = set()
    for token in tokens:
        token = token.strip()
        if is_numeric(token):
            try:
                ref = Note.objects.get(id=int(token), user=note.user)
                if ref.id != note.id:
                    resolved_ids.add(ref.id)
            except Note.DoesNotExist:
                pass
        else:
            try:
                ref = Note.objects.get(title=token, user=note.user)
                if ref.id != note.id:
                    resolved_ids.add(ref.id)
            except Note.DoesNotExist:
                pass
            except Note.MultipleObjectsReturned:
                pass
    NoteReference.objects.filter(from_note=note).delete()
    for ref_id in resolved_ids:
        NoteReference.objects.create(from_note=note, to_note_id=ref_id)


def calculate_phq9_total(q1, q2, q3, q4, q5, q6, q7, q8, q9) -> int:
    return sum([q1, q2, q3, q4, q5, q6, q7, q8, q9])


def get_phq9_label(total_score: int) -> str:
    if total_score <= 4:
        return '안정적인 상태'
    elif total_score <= 9:
        return '약간 힘든 시기'
    elif total_score <= 14:
        return '돌봄이 필요한 시기'
    elif total_score <= 19:
        return '많이 힘든 시기'
    else:
        return '전문가와 이야기할 시기'


def get_mood_level(mood_score: int) -> str:
    if mood_score <= 3:
        return 'hard'
    elif mood_score <= 6:
        return 'okay'
    else:
        return 'good'


def search_notes(user, query: str):
    """Search user's notes by title/body. Returns queryset."""
    qs = Note.objects.filter(user=user)
    if query.strip():
        qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
    return qs.order_by('-created_at')


def get_pulse_calendar_data(user, year: int, month: int) -> list:
    """Return list of {date, mood_score, level} for a given month."""
    logs = (
        MoodLog.objects
        .filter(user=user, logged_at__year=year, logged_at__month=month)
        .annotate(day=TruncDate('logged_at'))
        .values('day')
        .annotate(avg_mood=Avg('mood_score'))
        .order_by('day')
    )
    result = []
    for log in logs:
        avg = round(log['avg_mood'])
        result.append({
            'date': str(log['day']),
            'mood_score': avg,
            'level': get_mood_level(avg),
        })
    return result


def get_mood_trend(user, days: int = 30) -> list:
    """Return last N days of mood logs for trend chart."""
    since = timezone.now() - datetime.timedelta(days=days)
    logs = (
        MoodLog.objects
        .filter(user=user, logged_at__gte=since)
        .order_by('logged_at')
        .values('logged_at', 'mood_score', 'energy_score', 'behavior_tags')
    )
    return [
        {
            'logged_at': log['logged_at'].isoformat(),
            'mood_score': log['mood_score'],
            'energy_score': log['energy_score'],
            'behavior_tags': log['behavior_tags'],
        }
        for log in logs
    ]


# ---------------------------------------------------------------------------
# Studio / Project services
# ---------------------------------------------------------------------------

def get_project_dict(project) -> dict:
    """Serialize a Project to a dict for API responses."""
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    active_logs = project.goal_logs.filter(is_deleted=False)
    weekly_count = active_logs.filter(logged_at__gte=week_start).count()
    done_count = active_logs.filter(is_done=True).count()
    last_log = active_logs.order_by('-logged_at', '-created_at').first()
    if last_log:
        preview = last_log.body[:60]
    else:
        preview = (project.goal_description or '')[:60]
    return {
        'id': project.id,
        'title': project.title,
        'description': project.description or '',
        'status': project.status,
        'goal_description': project.goal_description or '',
        'completed_notes': project.completed_notes or '',
        'color_hex': project.color_hex,
        'sort_order': project.sort_order,
        'note_count': project.project_notes.count(),
        'weekly_log_count': weekly_count,
        'done_log_count': done_count,
        'last_log_preview': preview,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat(),
    }


def get_projects_for_user(user, status: str = '') -> list:
    """Return ordered list of user's projects, optionally filtered by status."""
    qs = Project.objects.filter(user=user)
    if status and status in ('active', 'paused', 'done'):
        qs = qs.filter(status=status)
    return list(qs.order_by('sort_order', 'created_at'))


def reorder_projects(user, ordered_ids: list) -> None:
    """Update sort_order for a user's projects given an ordered list of IDs."""
    projects = {p.id: p for p in Project.objects.filter(user=user, id__in=ordered_ids)}
    for idx, pid in enumerate(ordered_ids):
        if pid in projects:
            projects[pid].sort_order = idx
            projects[pid].save(update_fields=['sort_order'])


def link_note_to_project(project, note) -> bool:
    """Link a note to a project. Returns True if created, False if already linked."""
    _, created = ProjectNote.objects.get_or_create(project=project, note=note)
    return created


def unlink_note_from_project(project, note) -> bool:
    """Unlink a note from a project. Returns True if deleted."""
    deleted, _ = ProjectNote.objects.filter(project=project, note=note).delete()
    return deleted > 0


# ---------------------------------------------------------------------------
# GoalLog services
# ---------------------------------------------------------------------------

def get_goallog_dict(log) -> dict:
    """Serialize a GoalLog to a dict for API responses."""
    return {
        'id': log.id,
        'project_id': log.project_id,
        'body': log.body,
        'is_done': log.is_done,
        'log_type': log.log_type,
        'logged_at': str(log.logged_at),
        'is_deleted': log.is_deleted,
        'created_at': log.created_at.isoformat(),
    }


def get_goal_logs_for_project(project, include_deleted: bool = False):
    """Return active GoalLogs for a project ordered by logged_at desc."""
    qs = project.goal_logs.all()
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return qs.order_by('-logged_at', '-created_at')


def get_behavior_tag_frequencies(user, days: int = 30) -> list:
    """Return behavior tag frequency list for the last N days, excluding no_pattern."""
    since = timezone.now() - datetime.timedelta(days=days)
    logs = MoodLog.objects.filter(
        user=user, logged_at__gte=since,
    ).exclude(behavior_tags='').values_list('behavior_tags', flat=True)

    counts = {}
    for tag_str in logs:
        for slug in tag_str.split(';'):
            slug = slug.strip()
            if slug and slug != 'no_pattern':
                counts[slug] = counts.get(slug, 0) + 1

    result = [
        {'slug': slug, 'count': cnt}
        for slug, cnt in sorted(counts.items(), key=lambda x: -x[1])
        if cnt >= 3
    ]
    return result[:3]
