from django.test import TestCase
from django.contrib.auth import get_user_model

from atelier.models import SparkTag, Note, NoteReference, MoodLog, PHQ9Log


def make_user(username):
    User = get_user_model()
    return User.objects.create_user(username=username, password='test', nickname=username)


class SparkTagModelTest(TestCase):
    def test_str(self):
        tag = SparkTag.objects.create(name='unique_test_tag', name_ko='아이디어', sort_order=1)
        self.assertEqual(str(tag), '아이디어')


class NoteModelTest(TestCase):
    def setUp(self):
        self.user = make_user('noteuser')
        self.tag = SparkTag.objects.create(name='test_tag_note', name_ko='테스트태그')

    def test_str_with_title(self):
        note = Note.objects.create(user=self.user, title='My Title', body='some body')
        self.assertEqual(str(note), 'My Title')

    def test_str_without_title(self):
        body = 'A' * 100
        note = Note.objects.create(user=self.user, body=body)
        self.assertEqual(str(note), body[:50])

    def test_tag_nullable(self):
        note = Note.objects.create(user=self.user, body='no tag')
        self.assertIsNone(note.tag)

    def test_default_is_pinned(self):
        note = Note.objects.create(user=self.user, body='test')
        self.assertFalse(note.is_pinned)


class NoteReferenceModelTest(TestCase):
    def setUp(self):
        self.user = make_user('refuser')
        self.a = Note.objects.create(user=self.user, body='Note A')
        self.b = Note.objects.create(user=self.user, body='Note B')

    def test_create_reference(self):
        ref = NoteReference.objects.create(from_note=self.a, to_note=self.b)
        self.assertEqual(ref.from_note, self.a)
        self.assertEqual(ref.to_note, self.b)

    def test_unique_together(self):
        NoteReference.objects.create(from_note=self.a, to_note=self.b)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            NoteReference.objects.create(from_note=self.a, to_note=self.b)


class PHQ9LogModelTest(TestCase):
    def setUp(self):
        self.user = make_user('phquser')

    def test_create_phq9_log(self):
        log = PHQ9Log.objects.create(
            user=self.user,
            q1=1, q2=2, q3=0, q4=1, q5=2, q6=0, q7=1, q8=2, q9=0,
            total_score=9,
        )
        self.assertEqual(log.total_score, 9)
        self.assertEqual(log.user, self.user)
