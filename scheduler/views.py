import json
import os
import random
from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import UserCompanion, Task, DailyPlan, TimerSession, DailySummary, RecurringTask, CompanionPreset


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dialogue(request):
    trigger = request.query_params.get('trigger', '').strip()
    if not trigger:
        return Response({'text': ''})

    try:
        companion = request.user.companion
    except UserCompanion.DoesNotExist:
        return Response({'text': ''})

    options = companion.preset.dialogue_map.get(trigger)
    if not options:
        return Response({'text': ''})

    text = random.choice(options) if isinstance(options, list) else str(options)

    context = {k: v for k, v in request.query_params.items() if k != 'trigger'}
    for key, value in context.items():
        text = text.replace(f'{{{{{key}}}}}', value)

    return Response({'text': text, 'trigger': trigger})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)

    if task.daily_plan.user != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    point_reward = task.point_reward
    # task.status = Task.Status.DONE 위에 추가
    if task.status == Task.Status.DONE:
        return Response({'detail': 'Already completed.'}, status=status.HTTP_400_BAD_REQUEST)
    task.status = Task.Status.DONE
    task.save(update_fields=['status'])

    user = request.user
    user.points += point_reward
    user.save(update_fields=['points'])

    plan_tasks = task.daily_plan.tasks.all()
    total = plan_tasks.count()
    done_count = plan_tasks.filter(status=Task.Status.DONE).count()

    extra_trigger = None
    if done_count == total:
        extra_trigger = 'all_tasks_done'
    elif total >= 2 and done_count * 2 == total:
        extra_trigger = 'cheer_halfway'
    elif done_count == 1:
        extra_trigger = 'cheer_first_task'

    return Response({
        'status': task.status,
        'points_earned': point_reward,
        'total_points': user.points,
        'done_count': done_count,
        'total': total,
        'extra_trigger': extra_trigger,
    })


# ── helpers ──────────────────────────────────────────────────────────────────

VALID_DAYS = {'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'}


def _serialize_task(task):
    return {
        'id': task.id,
        'title': task.title,
        'planned_start': task.planned_start,
        'planned_duration_min': task.planned_duration,
        'point_reward': task.point_reward,
        'status': task.status,
        'display_order': task.display_order,
    }


def _serialize_recurring(rt):
    return {
        'id': rt.id,
        'title': rt.title,
        'planned_duration_min': rt.planned_duration,
        'point_reward': rt.point_reward,
        'recurrence_rule': rt.recurrence_rule,
        'preferred_time': rt.preferred_time,
    }


# ── 1. 오늘 계획 생성 ────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_today_plan(request):
    today = date.today()
    plan, created = DailyPlan.objects.get_or_create(
        user=request.user,
        plan_date=today,
        defaults={'status': DailyPlan.Status.DRAFT},
    )

    today_weekday = today.strftime('%a').upper()
    existing_titles = set(plan.tasks.values_list('title', flat=True))
    next_order = plan.tasks.count()

    for rt in RecurringTask.objects.filter(user=request.user, is_active=True):
        rule_days = [d.strip() for d in rt.recurrence_rule.split(',')]
        if today_weekday not in rule_days or rt.title in existing_titles:
            continue
        Task.objects.create(
            daily_plan=plan,
            title=rt.title,
            planned_start=rt.preferred_time,
            planned_duration=rt.planned_duration,
            point_reward=rt.point_reward,
            display_order=next_order,
        )
        existing_titles.add(rt.title)
        next_order += 1

    tasks = list(plan.tasks.order_by('display_order'))
    return Response({
        'id': plan.id,
        'plan_date': plan.plan_date,
        'created': created,
        'tasks': [_serialize_task(t) for t in tasks],
    })


# ── 2. 오늘 계획 조회 ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_today_plan(request):
    plan = get_object_or_404(DailyPlan, user=request.user, plan_date=date.today())
    tasks = list(plan.tasks.order_by('display_order'))
    return Response({
        'id': plan.id,
        'plan_date': plan.plan_date,
        'status': plan.status,
        'tasks': [_serialize_task(t) for t in tasks],
    })


# ── 3. 태스크 건너뛰기 ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def skip_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if task.daily_plan.user != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if task.status == Task.Status.DONE:
        return Response({'detail': 'Already completed.'}, status=status.HTTP_400_BAD_REQUEST)
    task.status = Task.Status.SKIPPED
    task.save(update_fields=['status'])
    return Response({'id': task.id, 'status': task.status})


# ── 4. 타이머 시작 ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_timer(request):
    task_id = request.data.get('task_id')
    session_type = request.data.get('session_type')

    task = get_object_or_404(Task, pk=task_id)
    if task.daily_plan.user != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    open_session = TimerSession.objects.filter(
        task__daily_plan__user=request.user,
        ended_at__isnull=True,
    ).exists()
    if open_session:
        return Response({'detail': 'Already running.'}, status=status.HTTP_400_BAD_REQUEST)

    session = TimerSession.objects.create(
        task=task,
        session_type=session_type,
        started_at=timezone.now(),
    )
    return Response({
        'id': session.id,
        'task_id': task.id,
        'session_type': session.session_type,
        'started_at': session.started_at,
    })


# ── 5. 타이머 종료 ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_timer(request):
    session_id = request.data.get('session_id')
    session = get_object_or_404(TimerSession, pk=session_id)

    if session.task.daily_plan.user != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if session.ended_at is not None:
        return Response({'detail': 'Already stopped.'}, status=status.HTTP_400_BAD_REQUEST)

    session.ended_at = timezone.now()
    session.save(update_fields=['ended_at'])
    elapsed_seconds = int((session.ended_at - session.started_at).total_seconds())

    return Response({
        'id': session.id,
        'session_type': session.session_type,
        'started_at': session.started_at,
        'ended_at': session.ended_at,
        'elapsed_seconds': elapsed_seconds,
    })


# ── 6. 하루 결산 ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_summary(request, plan_id):
    plan = get_object_or_404(DailyPlan, pk=plan_id)
    if plan.user != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        s = plan.summary
        return Response({
            'plan_date': plan.plan_date,
            'tasks_total': s.tasks_total,
            'tasks_done': s.completed_tasks,
            'points_earned': s.points_earned,
            'focus_minutes': s.total_focus_minutes,
            'break_minutes': s.break_minutes,
            'adherence_pct': s.adherence_pct,
        })
    except DailySummary.DoesNotExist:
        pass

    tasks = plan.tasks.all()
    tasks_total = tasks.count()
    tasks_done_qs = tasks.filter(status=Task.Status.DONE)
    tasks_done = tasks_done_qs.count()
    points_earned = sum(t.point_reward for t in tasks_done_qs)

    focus_secs = break_secs = 0
    for sess in TimerSession.objects.filter(task__daily_plan=plan, ended_at__isnull=False):
        elapsed = int((sess.ended_at - sess.started_at).total_seconds())
        if sess.session_type == TimerSession.SessionType.FOCUS:
            focus_secs += elapsed
        else:
            break_secs += elapsed

    adherence_pct = round(tasks_done / tasks_total * 100, 1) if tasks_total > 0 else 0.0

    s = DailySummary.objects.create(
        daily_plan=plan,
        tasks_total=tasks_total,
        completed_tasks=tasks_done,
        points_earned=points_earned,
        total_focus_minutes=focus_secs // 60,
        break_minutes=break_secs // 60,
        adherence_pct=adherence_pct,
    )
    return Response({
        'plan_date': plan.plan_date,
        'tasks_total': s.tasks_total,
        'tasks_done': s.completed_tasks,
        'points_earned': s.points_earned,
        'focus_minutes': s.total_focus_minutes,
        'break_minutes': s.break_minutes,
        'adherence_pct': s.adherence_pct,
    })


# ── 7. 주간 트래킹 ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weekly_history(request):
    week_offset = int(request.query_params.get('week_offset', 0))
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)

    summaries = {
        s.daily_plan.plan_date: s
        for s in DailySummary.objects.filter(
            daily_plan__user=request.user,
            daily_plan__plan_date__range=(monday, sunday),
        ).select_related('daily_plan')
    }

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        s = summaries.get(d)
        days.append({
            'date': d,
            'tasks_total': s.tasks_total if s else None,
            'tasks_done': s.completed_tasks if s else None,
            'points_earned': s.points_earned if s else None,
            'adherence_pct': s.adherence_pct if s else None,
        })

    return Response({'week_start': monday, 'week_end': sunday, 'days': days})


# ── 8. 반복 일정 목록/등록 ───────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def recurring_tasks(request):
    if request.method == 'GET':
        rts = RecurringTask.objects.filter(user=request.user)
        return Response([_serialize_recurring(rt) for rt in rts])

    title = request.data.get('title', '').strip()
    recurrence_rule = request.data.get('recurrence_rule', '').strip()
    planned_duration_min = request.data.get('planned_duration_min')
    point_reward = request.data.get('point_reward', 10)
    preferred_time = request.data.get('preferred_time') or None

    if not title:
        return Response({'detail': 'title is required.'}, status=status.HTTP_400_BAD_REQUEST)

    rule_days = [d.strip().upper() for d in recurrence_rule.split(',') if d.strip()]
    invalid = [d for d in rule_days if d not in VALID_DAYS]
    if not rule_days or invalid:
        return Response(
            {'detail': 'Invalid recurrence_rule. Use MON TUE WED THU FRI SAT SUN comma-separated.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rt = RecurringTask.objects.create(
        user=request.user,
        title=title,
        recurrence_rule=','.join(rule_days),
        planned_duration=planned_duration_min,
        point_reward=point_reward,
        preferred_time=preferred_time,
    )
    return Response(_serialize_recurring(rt), status=status.HTTP_201_CREATED)


# ── 반복 일정 삭제 ────────────────────────────────────────────────────────────

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_recurring_task(request, task_id):
    rt = get_object_or_404(RecurringTask, pk=task_id)
    if rt.user != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    rt.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── 커스텀 동반자 프리셋 ──────────────────────────────────────────────────────

_ALLOWED_IMAGE_EXTS = {'.png', '.gif', '.webp', '.jpg', '.jpeg'}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def _serialize_preset(preset, request=None):
    image_url = None
    if preset.image:
        image_url = (
            request.build_absolute_uri(preset.image.url)
            if request else preset.image.url
        )
    return {
        'id': preset.id,
        'name': preset.name,
        'animal_emoji': preset.animal_emoji,
        'theme_color': preset.theme_color,
        'dialogue_map': preset.dialogue_map,
        'system_prompt': preset.system_prompt,
        'image_url': image_url,
        'is_default': preset.is_default,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def companion_presets(request):
    if request.method == 'GET':
        presets = CompanionPreset.objects.filter(
            Q(created_by=request.user) | Q(is_default=True)
        ).order_by('-is_default', 'id')
        return Response([_serialize_preset(p, request) for p in presets])

    # POST — multipart/form-data
    name = request.data.get('name', '').strip()
    if not name:
        return Response({'detail': 'name is required.'}, status=status.HTTP_400_BAD_REQUEST)

    image_file = request.FILES.get('image')
    if image_file:
        ext = os.path.splitext(image_file.name)[1].lower()
        if ext not in _ALLOWED_IMAGE_EXTS:
            return Response(
                {'detail': '이미지는 png, gif, webp, jpg만 허용됩니다'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if image_file.size > _MAX_IMAGE_BYTES:
            return Response(
                {'detail': '이미지 파일 크기는 5MB 이하여야 합니다.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    raw_map = request.data.get('dialogue_map', '{}')
    try:
        dialogue_map = json.loads(raw_map) if isinstance(raw_map, str) else raw_map
    except (json.JSONDecodeError, TypeError):
        dialogue_map = {}

    preset = CompanionPreset.objects.create(
        created_by=request.user,
        is_default=False,
        name=name,
        animal_emoji=request.data.get('animal_emoji', ''),
        theme_color=request.data.get('theme_color', ''),
        dialogue_map=dialogue_map,
        system_prompt=request.data.get('system_prompt', ''),
        image=image_file,
    )
    return Response(_serialize_preset(preset, request), status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_companion_preset(request, preset_id):
    preset = get_object_or_404(CompanionPreset, pk=preset_id)
    if preset.created_by != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if preset.is_default:
        return Response({'detail': 'Cannot delete default preset.'}, status=status.HTTP_400_BAD_REQUEST)
    preset.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def activate_companion_preset(request, preset_id):
    preset = get_object_or_404(CompanionPreset, pk=preset_id)
    if not preset.is_default and preset.created_by != request.user:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    companion, _ = UserCompanion.objects.get_or_create(
        user=request.user,
        defaults={'preset': preset},
    )
    companion.preset = preset
    companion.save(update_fields=['preset'])
    return Response({'activated': preset.id})


# ── companion/me ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_companion(request):
    try:
        companion = request.user.companion
    except UserCompanion.DoesNotExist:
        default_preset = CompanionPreset.objects.filter(is_default=True).first()
        if not default_preset:
            return Response({'detail': 'No default preset configured.'}, status=status.HTTP_404_NOT_FOUND)
        companion = UserCompanion.objects.create(user=request.user, preset=default_preset)

    preset = companion.preset
    image_url = (
        request.build_absolute_uri(preset.image.url)
        if preset.image else None
    )
    return Response({
        'preset': {
            'name': preset.name,
            'animal_emoji': preset.animal_emoji,
            'theme_color': preset.theme_color,
            'image_url': image_url,
        },
        'nickname': request.user.nickname,
        'affection_level': companion.affection_level,
    })


# ── 페이지 뷰 ──────────────────────────────────────────────────────────────────

@login_required
def page_today(request):
    return render(request, 'scheduler/today.html')


@login_required
def page_summary(request, plan_id):
    return render(request, 'scheduler/summary.html', {'plan_id': plan_id})


@login_required
def page_history(request):
    return render(request, 'scheduler/history.html')


@login_required
def page_recurring(request):
    return render(request, 'scheduler/recurring.html')
