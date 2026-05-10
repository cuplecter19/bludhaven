# leitner/views.py
import csv
from datetime import date
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Word, WordSense, UserCard
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
import json


@login_required
def dashboard(request):
    user = request.user
    today = date.today()

    quiz_card = UserCard.objects.filter(
        user=user, next_review_at__lte=today
    ).order_by('?').first()

    difficult_cards = UserCard.objects.filter(user=user).order_by('-wrong_count')[:5]

    context = {
        'quiz_card': quiz_card,
        'due_cards_count': UserCard.objects.filter(user=user, next_review_at__lte=today).count(),
        'total_cards_count': UserCard.objects.filter(user=user).count(),
        'difficult_cards': difficult_cards,
    }
    return render(request, 'leitner/dashboard.html', context)


@login_required
def upload_words(request):
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'CSV 파일만 업로드 가능합니다.')
            return redirect('leitner:dashboard')

        try:
            decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
            reader = csv.DictReader(decoded_file)

            # 필수 컬럼 검사
            required_columns = {'word', 'meaning'}
            if not required_columns.issubset(reader.fieldnames or []):
                messages.error(request, "CSV에 'word'와 'meaning' 컬럼이 반드시 있어야 합니다.")
                return redirect('leitner:dashboard')

            count = 0
            for row in reader:
                word_obj, _ = Word.objects.update_or_create(
                    word=row['word'].strip().lower(),
                    defaults={
                        'pronunciation': row.get('pronunciation', ''),
                        'part_of_speech': row.get('part_of_speech', '')
                    }
                )

                sense_obj, _ = WordSense.objects.get_or_create(
                    word=word_obj,
                    meaning=row['meaning'].strip(),
                    defaults={
                        'example_en': row.get('example_en', ''),
                        'example_ko': row.get('example_ko', ''),
                        'context_tag': row.get('context_tag', '기초')
                    }
                )

                _, card_created = UserCard.objects.get_or_create(
                    user=request.user,
                    sense=sense_obj
                )

                if card_created:
                    count += 1

            messages.success(request, f"{count}개의 새로운 단어가 학습장에 추가되었습니다.")
            return redirect('leitner:dashboard')

        except Exception as e:
            messages.error(request, f"파일 처리 중 오류 발생: {e}")
            return redirect('leitner:dashboard')

    return redirect('leitner:dashboard')

@login_required
@require_POST
def submit_answer(request):
    data = json.loads(request.body)
    card_id = data.get('card_id')
    is_correct = data.get('is_correct')
    response_ms = data.get('response_ms')

    try:
        card = UserCard.objects.get(id=card_id, user=request.user)
    except UserCard.DoesNotExist:
        return JsonResponse({'error': '카드를 찾을 수 없습니다.'}, status=404)

    card.calculate_next_review(is_correct=is_correct, response_ms=response_ms)

    # 포인트 지급
    if is_correct:
        POINT_MAP = {1: 5, 2: 8, 3: 12, 4: 18, 5: 25}  # 높은 박스일수록 더 많은 포인트
        points = POINT_MAP.get(card.box_number, 5)
        request.user.points += points
        request.user.save(update_fields=['points'])

    return JsonResponse({
        'box_after': card.box_number,
        'next_review_at': str(card.next_review_at),
        'points_earned': points if is_correct else 0,
    })

@login_required
def word_list(request):
    """내 단어장 조회"""
    search_query = request.GET.get('search', '')
    
    # 1. 내 카드들을 가져오되, 단어와 뜻 정보를 미리 연결해서 가져옴 (성능 최적화)
    cards = UserCard.objects.filter(user=request.user).select_related('sense__word')
    
    # 2. 검색어가 있다면 단어 또는 뜻에서 검색
    if search_query:
        cards = cards.filter(
            Q(sense__word__word__icontains=search_query) | 
            Q(sense__meaning__icontains=search_query)
        )
        
    # 3. 박스 번호 순, 그 다음 단어 알파벳 순으로 정렬
    cards = cards.order_by('box_number', 'sense__word__word')
    
    return render(request, 'leitner/word_list.html', {
        'cards': cards,
        'search_query': search_query
    })