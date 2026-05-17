from django.test import TestCase
from django.contrib.auth import get_user_model

from atelier.models import SparkTag, Note, NoteReference
from atelier.utils import extract_references, is_numeric
from atelier.services import (
    sync_references,
    calculate_phq9_total,
    get_phq9_label,
    get_mood_level,
    search_notes,
)


def make_user(username):
    User = get_user_model()
    return User.objects.create_user(username=username, password='test', nickname=username)


class ExtractReferencesTest(TestCase):
    def test_numeric_token(self):
        result = extract_references('See [[123]] here')
        self.assertEqual(result, ['123'])

    def test_title_token(self):
        result = extract_references('See [[My Note]] here')
        self.assertEqual(result, ['My Note'])

    def test_multiple(self):
        result = extract_references('[[A]] and [[B]]')
        self.assertEqual(result, ['A', 'B'])

    def test_none(self):
        result = extract_references('No refs here')
        self.assertEqual(result, [])

    def test_is_numeric_true(self):
        self.assertTrue(is_numeric('  42  '))

    def test_is_numeric_false(self):
        self.assertFalse(is_numeric('hello'))


class SyncReferencesTest(TestCase):
    def setUp(self):
        self.user = make_user('syncuser')
        self.note_a = Note.objects.create(user=self.user, title='Alpha', body='some text')
        self.note_b = Note.objects.create(user=self.user, title='Beta', body='other text')

    def test_creates_reference_by_id(self):
        self.note_a.body = f'See [[{self.note_b.id}]]'
        self.note_a.save()
        sync_references(self.note_a)
        self.assertEqual(NoteReference.objects.filter(from_note=self.note_a, to_note=self.note_b).count(), 1)

    def test_creates_reference_by_title(self):
        self.note_a.body = '[[Beta]]'
        self.note_a.save()
        sync_references(self.note_a)
        self.assertEqual(NoteReference.objects.filter(from_note=self.note_a, to_note=self.note_b).count(), 1)

    def test_ignores_self_reference(self):
        self.note_a.body = f'[[{self.note_a.id}]]'
        self.note_a.save()
        sync_references(self.note_a)
        self.assertEqual(NoteReference.objects.filter(from_note=self.note_a).count(), 0)

    def test_ignores_nonexistent_ref(self):
        self.note_a.body = '[[99999]]'
        self.note_a.save()
        sync_references(self.note_a)
        self.assertEqual(NoteReference.objects.filter(from_note=self.note_a).count(), 0)

    def test_updates_refs_on_resync(self):
        self.note_a.body = f'[[{self.note_b.id}]]'
        self.note_a.save()
        sync_references(self.note_a)
        # Now remove reference
        self.note_a.body = 'no refs'
        self.note_a.save()
        sync_references(self.note_a)
        self.assertEqual(NoteReference.objects.filter(from_note=self.note_a).count(), 0)


class CalculatePHQ9TotalTest(TestCase):
    def test_zero_all(self):
        self.assertEqual(calculate_phq9_total(0, 0, 0, 0, 0, 0, 0, 0, 0), 0)

    def test_max_all(self):
        self.assertEqual(calculate_phq9_total(3, 3, 3, 3, 3, 3, 3, 3, 3), 27)

    def test_mixed(self):
        self.assertEqual(calculate_phq9_total(1, 2, 0, 1, 2, 0, 1, 2, 0), 9)


class GetPHQ9LabelTest(TestCase):
    def test_stable(self):
        self.assertEqual(get_phq9_label(0), '안정적인 상태')
        self.assertEqual(get_phq9_label(4), '안정적인 상태')

    def test_mild(self):
        self.assertEqual(get_phq9_label(5), '약간 힘든 시기')
        self.assertEqual(get_phq9_label(9), '약간 힘든 시기')

    def test_moderate(self):
        self.assertEqual(get_phq9_label(10), '돌봄이 필요한 시기')
        self.assertEqual(get_phq9_label(14), '돌봄이 필요한 시기')

    def test_moderately_severe(self):
        self.assertEqual(get_phq9_label(15), '많이 힘든 시기')
        self.assertEqual(get_phq9_label(19), '많이 힘든 시기')

    def test_severe(self):
        self.assertEqual(get_phq9_label(20), '전문가와 이야기할 시기')
        self.assertEqual(get_phq9_label(27), '전문가와 이야기할 시기')


class GetMoodLevelTest(TestCase):
    def test_hard(self):
        self.assertEqual(get_mood_level(1), 'hard')
        self.assertEqual(get_mood_level(3), 'hard')

    def test_okay(self):
        self.assertEqual(get_mood_level(4), 'okay')
        self.assertEqual(get_mood_level(6), 'okay')

    def test_good(self):
        self.assertEqual(get_mood_level(7), 'good')
        self.assertEqual(get_mood_level(10), 'good')


class SearchNotesTest(TestCase):
    def setUp(self):
        self.user = make_user('searchuser')
        Note.objects.create(user=self.user, title='Django Tips', body='about django framework')
        Note.objects.create(user=self.user, title='Python Guide', body='all about python')
        Note.objects.create(user=self.user, title='Other', body='unrelated')

    def test_search_by_title(self):
        results = search_notes(self.user, 'Django')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().title, 'Django Tips')

    def test_search_by_body(self):
        results = search_notes(self.user, 'python')
        self.assertEqual(results.count(), 1)

    def test_empty_query_returns_all(self):
        results = search_notes(self.user, '')
        self.assertEqual(results.count(), 3)

    def test_does_not_return_other_users_notes(self):
        other = make_user('otheruser2')
        Note.objects.create(user=other, title='Django Secret', body='secret')
        results = search_notes(self.user, 'Django')
        self.assertEqual(results.count(), 1)
