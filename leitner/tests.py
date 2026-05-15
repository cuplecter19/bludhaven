from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ReviewLog, UserCard, Word, WordSense


class LeitnerViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tester',
            password='pass1234',
            nickname='tester',
            email='tester@example.com',
        )
        self.client.force_login(self.user)

        word = Word.objects.create(word='apple')
        sense = WordSense.objects.create(word=word, meaning='사과')
        self.card = UserCard.objects.create(user=self.user, sense=sense, box_number=3)

    def test_word_list_includes_box_counts(self):
        response = self.client.get(reverse('leitner:word_list'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('box_counts', response.context)
        self.assertEqual(response.context['box_counts'][3], 1)
        self.assertEqual(response.context['box_counts'][1], 0)

    def test_review_log_page_renders(self):
        ReviewLog.objects.create(
            user=self.user,
            card=self.card,
            is_correct=True,
            box_before=2,
            box_after=3,
            response_ms=1000,
        )

        response = self.client.get(reverse('leitner:review_log'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LEARNING LOG')
        self.assertContains(response, self.card.sense.word.word)
