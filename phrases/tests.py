import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.timezone import localdate

from .models import DailySummary, PhraseCard, ReviewLog, ScrambleAttempt, Tag
from .services import get_due_cards, process_review, should_offer_scramble

User = get_user_model()


def make_user(username, nickname=None):
    return User.objects.create_user(
        username=username,
        password='testpass123',
        nickname=nickname or username,
    )


class TagModelTest(TestCase):
    def test_str(self):
        tag = Tag(name='phrasal_verb', name_ko='구동사')
        self.assertEqual(str(tag), 'phrasal_verb')


class PhraseCardClozeTest(TestCase):
    def setUp(self):
        self.user = make_user('tester')
        self.card = PhraseCard.objects.create(
            user=self.user,
            sentence_en='She always [looks up to] her mentor.',
            sentence_ko='그녀는 항상 자신의 멘토를 존경한다.',
            phrase='looks up to',
            phrase_ko='~을 존경하다',
        )

    def test_get_display_sentence(self):
        self.assertEqual(
            self.card.get_display_sentence(),
            'She always looks up to her mentor.',
        )

    def test_get_cloze_data_no_hint(self):
        data = self.card.get_cloze_data()
        blank = next(s for s in data['segments'] if s['type'] == 'blank')
        self.assertEqual(blank['answer'], 'looks up to')
        self.assertEqual(blank['hint'], '')

    def test_get_cloze_data_with_hint(self):
        card = PhraseCard(
            user=self.user,
            sentence_en='Fashion is [ephemeral/일시적인], but style endures.',
            sentence_ko='',
            phrase='ephemeral',
            phrase_ko='',
        )
        data = card.get_cloze_data()
        blank = next(s for s in data['segments'] if s['type'] == 'blank')
        self.assertEqual(blank['answer'], 'ephemeral')
        self.assertEqual(blank['hint'], '일시적인')

    def test_get_cloze_data_text_segments(self):
        data = self.card.get_cloze_data()
        texts = [s['value'] for s in data['segments'] if s['type'] == 'text']
        self.assertIn('She always ', texts)
        self.assertIn(' her mentor.', texts)

    def test_get_scramble_words_reproducible(self):
        data1 = self.card.get_scramble_words(seed=42)
        data2 = self.card.get_scramble_words(seed=42)
        self.assertEqual(data1['shuffled'], data2['shuffled'])
        self.assertEqual(data1['correct_order'], data2['correct_order'])

    def test_get_scramble_words_correct_order(self):
        data = self.card.get_scramble_words(seed=0)
        self.assertEqual(
            data['correct_order'],
            ['She', 'always', 'looks', 'up', 'to', 'her', 'mentor.'],
        )

    def test_get_scramble_words_sorted_equals_correct(self):
        data = self.card.get_scramble_words(seed=7)
        self.assertEqual(sorted(data['shuffled']), sorted(data['correct_order']))


class ProcessReviewTest(TestCase):
    def setUp(self):
        self.user = make_user('reviewer')
        self.card = PhraseCard.objects.create(
            user=self.user,
            sentence_en='[Look into] this matter.',
            sentence_ko='이 문제를 조사해라.',
            phrase='Look into',
            phrase_ko='~을 조사하다',
            box_number=2,
        )

    def _process(self, result):
        return process_review(self.card, result=result, mode=ReviewLog.MODE_CLOZE)

    def test_again_resets_box_to_1(self):
        outcome = self._process(ReviewLog.RESULT_AGAIN)
        self.card.refresh_from_db()
        self.assertEqual(self.card.box_number, 1)
        self.assertEqual(self.card.next_review_at, localdate())
        self.assertEqual(self.card.correct_streak, 0)
        self.assertFalse(outcome['offer_scramble'])

    def test_hard_keeps_box(self):
        self._process(ReviewLog.RESULT_HARD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.box_number, 2)
        self.assertEqual(self.card.correct_streak, 0)

    def test_good_advances_box(self):
        self._process(ReviewLog.RESULT_GOOD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.box_number, 3)
        self.assertEqual(self.card.correct_streak, 1)

    def test_easy_advances_box_and_doubles_interval(self):
        from datetime import timedelta
        self._process(ReviewLog.RESULT_EASY)
        self.card.refresh_from_db()
        self.assertEqual(self.card.box_number, 3)
        # box 3 interval = 7 days × 2 = 14
        self.assertEqual(self.card.next_review_at, localdate() + timedelta(days=14))

    def test_good_offers_scramble(self):
        outcome = self._process(ReviewLog.RESULT_GOOD)
        self.assertTrue(outcome['offer_scramble'])

    def test_again_does_not_offer_scramble(self):
        outcome = self._process(ReviewLog.RESULT_AGAIN)
        self.assertFalse(outcome['offer_scramble'])

    def test_review_count_increments(self):
        self._process(ReviewLog.RESULT_GOOD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.review_count, 1)

    def test_last_reviewed_at_set_today(self):
        self._process(ReviewLog.RESULT_GOOD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.last_reviewed_at, localdate())

    def test_box_capped_at_5(self):
        self.card.box_number = 5
        self.card.save()
        self._process(ReviewLog.RESULT_GOOD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.box_number, 5)

    def test_review_log_created(self):
        self._process(ReviewLog.RESULT_GOOD)
        log = ReviewLog.objects.get(card=self.card)
        self.assertEqual(log.result, ReviewLog.RESULT_GOOD)
        self.assertEqual(log.mode, ReviewLog.MODE_CLOZE)
        self.assertEqual(log.box_before, 2)
        self.assertEqual(log.box_after, 3)

    def test_daily_summary_cloze_reviewed(self):
        self._process(ReviewLog.RESULT_GOOD)
        summary = DailySummary.objects.get(user=self.user, date=localdate())
        self.assertEqual(summary.cloze_reviewed, 1)
        self.assertEqual(summary.cloze_correct, 1)

    def test_daily_summary_again_not_counted_as_correct(self):
        self._process(ReviewLog.RESULT_AGAIN)
        summary = DailySummary.objects.get(user=self.user, date=localdate())
        self.assertEqual(summary.cloze_reviewed, 1)
        self.assertEqual(summary.cloze_correct, 0)

    def test_streak_resets_on_hard(self):
        self.card.correct_streak = 3
        self.card.save()
        self._process(ReviewLog.RESULT_HARD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.correct_streak, 0)

    def test_streak_accumulates_on_good(self):
        self._process(ReviewLog.RESULT_GOOD)
        self.card.refresh_from_db()
        self._process(ReviewLog.RESULT_GOOD)
        self.card.refresh_from_db()
        self.assertEqual(self.card.correct_streak, 2)


class GetDueCardsTest(TestCase):
    def setUp(self):
        from datetime import date, timedelta
        self.user = make_user('duetester')
        # due card
        PhraseCard.objects.create(
            user=self.user,
            sentence_en='[a].',
            sentence_ko='',
            phrase='a',
            phrase_ko='',
            next_review_at=date.today(),
        )
        # future card – not due yet
        PhraseCard.objects.create(
            user=self.user,
            sentence_en='[b].',
            sentence_ko='',
            phrase='b',
            phrase_ko='',
            next_review_at=date.today() + timedelta(days=5),
        )
        # inactive card – should be excluded
        PhraseCard.objects.create(
            user=self.user,
            sentence_en='[c].',
            sentence_ko='',
            phrase='c',
            phrase_ko='',
            next_review_at=date.today(),
            is_active=False,
        )

    def test_returns_only_due_active_cards(self):
        cards = get_due_cards(self.user)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].phrase, 'a')

    def test_limit_is_respected(self):
        cards = get_due_cards(self.user, limit=0)
        self.assertEqual(len(cards), 0)


class ShouldOfferScrambleTest(TestCase):
    def setUp(self):
        self.user = make_user('scrambletest')

    def _card(self, streak):
        return PhraseCard(
            user=self.user,
            sentence_en='[x].',
            sentence_ko='',
            phrase='x',
            phrase_ko='',
            correct_streak=streak,
        )

    def test_no_streak_returns_false(self):
        self.assertFalse(should_offer_scramble(self._card(0)))

    def test_streak_1_returns_true(self):
        self.assertTrue(should_offer_scramble(self._card(1)))

    def test_streak_3_returns_true(self):
        self.assertTrue(should_offer_scramble(self._card(3)))


class ApiTest(TestCase):
    def setUp(self):
        self.user = make_user('apiuser')
        self.client.login(username='apiuser', password='testpass123')
        self.card = PhraseCard.objects.create(
            user=self.user,
            sentence_en='She [looks up to] her mentor.',
            sentence_ko='그녀는 멘토를 존경한다.',
            phrase='looks up to',
            phrase_ko='~을 존경하다',
        )

    def test_api_cards_due(self):
        resp = self.client.get('/learn/phrases/api/cards/due/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('cards', data)
        self.assertIn('count', data)

    def test_api_cards_due_includes_cloze_data(self):
        resp = self.client.get('/learn/phrases/api/cards/due/')
        cards = resp.json()['cards']
        self.assertIn('cloze_data', cards[0])

    def test_api_card_detail(self):
        resp = self.client.get(f'/learn/phrases/api/cards/{self.card.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['phrase'], 'looks up to')

    def test_api_card_detail_404_other_user(self):
        other = make_user('other', nickname='othernick')
        card2 = PhraseCard.objects.create(
            user=other,
            sentence_en='[test].',
            sentence_ko='',
            phrase='test',
            phrase_ko='',
        )
        resp = self.client.get(f'/learn/phrases/api/cards/{card2.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_api_review_good(self):
        resp = self.client.post(
            '/learn/phrases/api/review/',
            data=json.dumps({'card_id': self.card.id, 'result': 'good'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('card_state', data)
        self.assertIn('offer_scramble', data)

    def test_api_review_invalid_result(self):
        resp = self.client.post(
            '/learn/phrases/api/review/',
            data=json.dumps({'card_id': self.card.id, 'result': 'perfect'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_review_card_not_found(self):
        resp = self.client.post(
            '/learn/phrases/api/review/',
            data=json.dumps({'card_id': 99999, 'result': 'good'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_api_scramble_correct(self):
        correct_order = self.card.get_scramble_words(seed=0)['correct_order']
        resp = self.client.post(
            '/learn/phrases/api/scramble/',
            data=json.dumps({'card_id': self.card.id, 'submitted_order': correct_order}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['is_correct'])

    def test_api_scramble_wrong(self):
        resp = self.client.post(
            '/learn/phrases/api/scramble/',
            data=json.dumps({'card_id': self.card.id, 'submitted_order': ['wrong', 'order']}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['is_correct'])

    def test_api_scramble_correct_order_returned(self):
        resp = self.client.post(
            '/learn/phrases/api/scramble/',
            data=json.dumps({'card_id': self.card.id, 'submitted_order': ['wrong']}),
            content_type='application/json',
        )
        self.assertIn('correct_order', resp.json())

    def test_api_stats(self):
        resp = self.client.get('/learn/phrases/api/stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('summaries', resp.json())

    def test_unauthenticated_redirects(self):
        self.client.logout()
        for url in [
            '/learn/phrases/',
            '/learn/phrases/cloze/',
            '/learn/phrases/scramble/',
            '/learn/phrases/stats/',
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, msg=url)
