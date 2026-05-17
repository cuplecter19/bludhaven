import json

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from atelier.models import SparkTag, Note, MoodLog, PHQ9Log


def make_user(username):
    User = get_user_model()
    return User.objects.create_user(username=username, password='test', nickname=username)


class PageViewsAuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user('pageuser')

    def _login(self):
        self.client.login(username='pageuser', password='test')

    def test_home_requires_login(self):
        resp = self.client.get(reverse('atelier:home'))
        self.assertEqual(resp.status_code, 302)

    def test_spark_list_requires_login(self):
        resp = self.client.get(reverse('atelier:spark_list'))
        self.assertEqual(resp.status_code, 302)

    def test_pulse_home_requires_login(self):
        resp = self.client.get(reverse('atelier:pulse_home'))
        self.assertEqual(resp.status_code, 302)

    def test_home_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:home'))
        self.assertEqual(resp.status_code, 200)

    def test_spark_list_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:spark_list'))
        self.assertEqual(resp.status_code, 200)

    def test_spark_new_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:spark_new'))
        self.assertEqual(resp.status_code, 200)

    def test_spark_detail_logged_in(self):
        self._login()
        note = Note.objects.create(user=self.user, body='test note')
        resp = self.client.get(reverse('atelier:spark_detail', args=[note.id]))
        self.assertEqual(resp.status_code, 200)

    def test_pulse_home_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:pulse_home'))
        self.assertEqual(resp.status_code, 200)

    def test_pulse_checkin_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:pulse_checkin'))
        self.assertEqual(resp.status_code, 200)

    def test_pulse_phq9_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:pulse_phq9'))
        self.assertEqual(resp.status_code, 200)


class NoteAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user('apiuser')
        self.client.login(username='apiuser', password='test')
        self.tag = SparkTag.objects.create(name='test_idea', name_ko='테스트아이디어')

    def test_create_note(self):
        resp = self.client.post(
            reverse('atelier:api_notes_list'),
            data=json.dumps({'body': 'Hello world'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['body_preview'], 'Hello world')

    def test_create_note_with_tag(self):
        resp = self.client.post(
            reverse('atelier:api_notes_list'),
            data=json.dumps({'body': 'Tagged', 'tag_id': self.tag.id}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['tag']['id'], self.tag.id)

    def test_get_notes_list(self):
        Note.objects.create(user=self.user, body='Note 1')
        Note.objects.create(user=self.user, body='Note 2')
        resp = self.client.get(reverse('atelier:api_notes_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 2)

    def test_get_note_detail(self):
        note = Note.objects.create(user=self.user, body='Detail note', title='Title')
        resp = self.client.get(reverse('atelier:api_note_detail', args=[note.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['title'], 'Title')

    def test_patch_note(self):
        note = Note.objects.create(user=self.user, body='Original')
        resp = self.client.patch(
            reverse('atelier:api_note_detail', args=[note.id]),
            data=json.dumps({'body': 'Updated', 'title': 'New Title'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['title'], 'New Title')
        note.refresh_from_db()
        self.assertEqual(note.body, 'Updated')

    def test_delete_note(self):
        note = Note.objects.create(user=self.user, body='To delete')
        resp = self.client.delete(reverse('atelier:api_note_detail', args=[note.id]))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Note.objects.filter(id=note.id).exists())

    def test_search_notes(self):
        Note.objects.create(user=self.user, body='unique keyword here')
        Note.objects.create(user=self.user, body='nothing special')
        resp = self.client.get(reverse('atelier:api_notes_search') + '?q=unique')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['notes']), 1)

    def test_create_note_missing_body(self):
        resp = self.client.post(
            reverse('atelier:api_notes_list'),
            data=json.dumps({'title': 'No body'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_other_user_cannot_access_note(self):
        other = make_user('other_api_user')
        note = Note.objects.create(user=other, body='Private')
        resp = self.client.get(reverse('atelier:api_note_detail', args=[note.id]))
        self.assertEqual(resp.status_code, 404)


class MoodAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user('mooduser')
        self.client.login(username='mooduser', password='test')

    def test_create_mood_log(self):
        resp = self.client.post(
            reverse('atelier:api_mood_list'),
            data=json.dumps({'mood_score': 7, 'energy_score': 5}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['mood_score'], 7)

    def test_get_mood_list(self):
        MoodLog.objects.create(user=self.user, mood_score=6)
        MoodLog.objects.create(user=self.user, mood_score=4)
        resp = self.client.get(reverse('atelier:api_mood_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['logs']), 2)

    def test_create_mood_missing_score(self):
        resp = self.client.post(
            reverse('atelier:api_mood_list'),
            data=json.dumps({'energy_score': 5}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class PHQ9APITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user('phq9user')
        self.client.login(username='phq9user', password='test')

    def _post_phq9(self, q_vals=None, q9_val=0):
        if q_vals is None:
            q_vals = {f'q{i}': 0 for i in range(1, 10)}
        q_vals['q9'] = q9_val
        return self.client.post(
            reverse('atelier:api_phq9_list'),
            data=json.dumps(q_vals),
            content_type='application/json',
        )

    def test_create_phq9_log(self):
        resp = self._post_phq9()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['total_score'], 0)

    def test_show_crisis_info_when_q9_ge_1(self):
        resp = self._post_phq9(q9_val=1)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['show_crisis_info'])

    def test_no_crisis_info_when_q9_is_0(self):
        resp = self._post_phq9(q9_val=0)
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.json()['show_crisis_info'])

    def test_total_score_calculated_server_side(self):
        vals = {f'q{i}': i % 4 for i in range(1, 10)}
        resp = self.client.post(
            reverse('atelier:api_phq9_list'),
            data=json.dumps(vals),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        expected = sum(i % 4 for i in range(1, 10))
        self.assertEqual(resp.json()['total_score'], expected)

    def test_get_phq9_list(self):
        PHQ9Log.objects.create(
            user=self.user, q1=0, q2=0, q3=0, q4=0, q5=0, q6=0, q7=0, q8=0, q9=0, total_score=0
        )
        resp = self.client.get(reverse('atelier:api_phq9_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['logs']), 1)


# ---------------------------------------------------------------------------
# Studio page & API tests
# ---------------------------------------------------------------------------

class StudioPageTest(TestCase):
    def setUp(self):
        from atelier.models import Project
        self.client = Client()
        self.user = make_user('studiouser')
        self.project = Project.objects.create(user=self.user, title='Test Project')

    def _login(self):
        self.client.login(username='studiouser', password='test')

    def test_studio_home_requires_login(self):
        resp = self.client.get(reverse('atelier:studio_home'))
        self.assertEqual(resp.status_code, 302)

    def test_studio_home_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:studio_home'))
        self.assertEqual(resp.status_code, 200)

    def test_studio_home_status_filter(self):
        self._login()
        resp = self.client.get(reverse('atelier:studio_home') + '?status=done')
        self.assertEqual(resp.status_code, 200)

    def test_studio_new_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:studio_new'))
        self.assertEqual(resp.status_code, 200)

    def test_studio_new_requires_login(self):
        resp = self.client.get(reverse('atelier:studio_new'))
        self.assertEqual(resp.status_code, 302)

    def test_studio_detail_logged_in(self):
        self._login()
        resp = self.client.get(reverse('atelier:studio_detail', args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)

    def test_studio_detail_requires_login(self):
        resp = self.client.get(reverse('atelier:studio_detail', args=[self.project.id]))
        self.assertEqual(resp.status_code, 302)

    def test_studio_detail_other_user_returns_404(self):
        other = make_user('other_studio')
        self._login()
        other_project = __import__('atelier.models', fromlist=['Project']).Project.objects.create(
            user=other, title='Other Project'
        )
        resp = self.client.get(reverse('atelier:studio_detail', args=[other_project.id]))
        self.assertEqual(resp.status_code, 404)


class ProjectAPITest(TestCase):
    def setUp(self):
        from atelier.models import Project
        self.client = Client()
        self.user = make_user('projapi')
        self.client.login(username='projapi', password='test')
        self.project = Project.objects.create(
            user=self.user,
            title='My Project',
            status='active',
        )

    def test_list_projects(self):
        resp = self.client.get(reverse('atelier:api_projects_list'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('projects', data)

    def test_list_projects_status_filter(self):
        resp = self.client.get(reverse('atelier:api_projects_list') + '?status=active')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(p['status'] == 'active' for p in resp.json()['projects']))

    def test_create_project(self):
        resp = self.client.post(
            reverse('atelier:api_projects_list'),
            data=json.dumps({'title': 'New Project', 'color_hex': '#4a7a8a'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['title'], 'New Project')
        self.assertEqual(data['color_hex'], '#4a7a8a')

    def test_create_project_missing_title(self):
        resp = self.client.post(
            reverse('atelier:api_projects_list'),
            data=json.dumps({'description': 'no title'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_project_detail(self):
        resp = self.client.get(reverse('atelier:api_project_detail', args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['title'], 'My Project')

    def test_patch_project(self):
        resp = self.client.patch(
            reverse('atelier:api_project_detail', args=[self.project.id]),
            data=json.dumps({'goal_description': 'Working on tests', 'status': 'paused'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['goal_description'], 'Working on tests')
        self.assertEqual(data['status'], 'paused')

    def test_delete_project(self):
        resp = self.client.delete(reverse('atelier:api_project_detail', args=[self.project.id]))
        self.assertEqual(resp.status_code, 204)
        from atelier.models import Project
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_other_user_cannot_access_project(self):
        other = make_user('other_proj')
        from atelier.models import Project
        other_proj = Project.objects.create(user=other, title='Other')
        resp = self.client.get(reverse('atelier:api_project_detail', args=[other_proj.id]))
        self.assertEqual(resp.status_code, 404)

    def test_link_note_to_project(self):
        note = Note.objects.create(user=self.user, body='A spark note')
        resp = self.client.post(
            reverse('atelier:api_project_notes', args=[self.project.id]),
            data=json.dumps({'note_id': note.id}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['linked'])

    def test_link_note_idempotent(self):
        note = Note.objects.create(user=self.user, body='Idempotent note')
        self.client.post(
            reverse('atelier:api_project_notes', args=[self.project.id]),
            data=json.dumps({'note_id': note.id}),
            content_type='application/json',
        )
        resp = self.client.post(
            reverse('atelier:api_project_notes', args=[self.project.id]),
            data=json.dumps({'note_id': note.id}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, (200, 201))

    def test_get_project_notes(self):
        note = Note.objects.create(user=self.user, body='A linked note')
        from atelier.models import ProjectNote
        ProjectNote.objects.create(project=self.project, note=note)
        resp = self.client.get(reverse('atelier:api_project_notes', args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['notes']), 1)

    def test_unlink_note_from_project(self):
        note = Note.objects.create(user=self.user, body='To unlink')
        from atelier.models import ProjectNote
        ProjectNote.objects.create(project=self.project, note=note)
        resp = self.client.delete(
            reverse('atelier:api_project_note_unlink', args=[self.project.id, note.id])
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ProjectNote.objects.filter(project=self.project, note=note).exists())

    def test_reorder_projects(self):
        from atelier.models import Project
        p2 = Project.objects.create(user=self.user, title='Second')
        resp = self.client.post(
            reverse('atelier:api_projects_reorder'),
            data=json.dumps({'ordered_ids': [p2.id, self.project.id]}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        p2.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(p2.sort_order, 0)
        self.assertEqual(self.project.sort_order, 1)


# ---------------------------------------------------------------------------
# Stage 5 tests
# ---------------------------------------------------------------------------

class SparkExportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user('exportuser')
        self.client.login(username='exportuser', password='test')
        self.note = Note.objects.create(
            user=self.user,
            title='My Note',
            body='# Hello\n\nWorld',
        )

    def test_export_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('atelier:spark_export', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)

    def test_export_returns_md_file(self):
        resp = self.client.get(reverse('atelier:spark_export', args=[self.note.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/markdown', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.md', resp['Content-Disposition'])

    def test_export_content_includes_title_and_body(self):
        resp = self.client.get(reverse('atelier:spark_export', args=[self.note.id]))
        content = resp.content.decode('utf-8')
        self.assertIn('My Note', content)
        self.assertIn('# Hello', content)
        self.assertIn('World', content)

    def test_export_note_without_title(self):
        note = Note.objects.create(user=self.user, body='Just a body')
        resp = self.client.get(reverse('atelier:spark_export', args=[note.id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Just a body', content)

    def test_export_other_user_returns_404(self):
        other = make_user('other_export')
        other_note = Note.objects.create(user=other, body='secret')
        resp = self.client.get(reverse('atelier:spark_export', args=[other_note.id]))
        self.assertEqual(resp.status_code, 404)


class PHQ9TrendAPITest(TestCase):
    def setUp(self):
        from atelier.models import PHQ9Log
        self.client = Client()
        self.user = make_user('phq9trend')
        self.client.login(username='phq9trend', password='test')
        # Create two PHQ9 logs
        PHQ9Log.objects.create(
            user=self.user, q1=1, q2=1, q3=1, q4=1, q5=1,
            q6=1, q7=1, q8=1, q9=0, total_score=8,
        )
        PHQ9Log.objects.create(
            user=self.user, q1=2, q2=2, q3=2, q4=2, q5=2,
            q6=2, q7=2, q8=2, q9=0, total_score=16,
        )

    def test_phq9_trend_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('atelier:api_phq9_trend'))
        self.assertEqual(resp.status_code, 302)

    def test_phq9_trend_returns_data(self):
        resp = self.client.get(reverse('atelier:api_phq9_trend'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('data', data)
        self.assertEqual(len(data['data']), 2)

    def test_phq9_trend_fields(self):
        resp = self.client.get(reverse('atelier:api_phq9_trend'))
        item = resp.json()['data'][0]
        self.assertIn('logged_at', item)
        self.assertIn('total_score', item)

    def test_phq9_trend_chronological_order(self):
        resp = self.client.get(reverse('atelier:api_phq9_trend'))
        dates = [d['logged_at'] for d in resp.json()['data']]
        self.assertEqual(dates, sorted(dates))


# ---------------------------------------------------------------------------
# Stage 6 tests — behavior_tags
# ---------------------------------------------------------------------------

class BehaviorTagsAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user('behavioruser')
        self.client.login(username='behavioruser', password='test')

    def test_create_mood_with_behavior_tags(self):
        resp = self.client.post(
            reverse('atelier:api_mood_list'),
            data=json.dumps({'mood_score': 6, 'behavior_tags': 'cant_start;scattered'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['behavior_tags'], 'cant_start;scattered')

    def test_create_mood_without_behavior_tags(self):
        resp = self.client.post(
            reverse('atelier:api_mood_list'),
            data=json.dumps({'mood_score': 7}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['behavior_tags'], '')

    def test_create_mood_invalid_behavior_slug(self):
        resp = self.client.post(
            reverse('atelier:api_mood_list'),
            data=json.dumps({'mood_score': 5, 'behavior_tags': 'not_a_slug'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_mood_list_includes_behavior_tags(self):
        MoodLog.objects.create(user=self.user, mood_score=5, behavior_tags='on_track')
        resp = self.client.get(reverse('atelier:api_mood_list'))
        self.assertEqual(resp.status_code, 200)
        logs = resp.json()['logs']
        self.assertIn('behavior_tags', logs[0])
        self.assertEqual(logs[0]['behavior_tags'], 'on_track')

    def test_pulse_trend_includes_behavior_tags(self):
        MoodLog.objects.create(user=self.user, mood_score=5, behavior_tags='exhausted')
        resp = self.client.get(reverse('atelier:api_pulse_trend'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(any('behavior_tags' in item for item in data))

    def test_no_pattern_is_valid_slug(self):
        resp = self.client.post(
            reverse('atelier:api_mood_list'),
            data=json.dumps({'mood_score': 5, 'behavior_tags': 'no_pattern'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['behavior_tags'], 'no_pattern')

    def test_checkin_page_has_behavior_tags(self):
        resp = self.client.get(reverse('atelier:pulse_checkin'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'cant_start')
        self.assertContains(resp, 'no_pattern')


# ---------------------------------------------------------------------------
# Stage 6 tests — GoalLog
# ---------------------------------------------------------------------------

class GoalLogAPITest(TestCase):
    def setUp(self):
        from atelier.models import Project
        self.client = Client()
        self.user = make_user('goalloguser')
        self.client.login(username='goalloguser', password='test')
        self.project = Project.objects.create(user=self.user, title='My Goal')

    def _logs_url(self):
        return reverse('atelier:api_goal_logs_list', args=[self.project.id])

    def _log_url(self, log_id):
        return reverse('atelier:api_goal_log_detail', args=[self.project.id, log_id])

    def test_create_goal_log(self):
        resp = self.client.post(
            self._logs_url(),
            data=json.dumps({'body': 'Today I worked on tests.', 'log_type': 'done'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['body'], 'Today I worked on tests.')
        self.assertEqual(data['log_type'], 'done')
        self.assertFalse(data['is_done'])

    def test_create_goal_log_missing_body(self):
        resp = self.client.post(
            self._logs_url(),
            data=json.dumps({'log_type': 'note'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_goal_logs(self):
        from atelier.models import GoalLog
        GoalLog.objects.create(project=self.project, user=self.user, body='Log 1')
        GoalLog.objects.create(project=self.project, user=self.user, body='Log 2')
        resp = self.client.get(self._logs_url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['logs']), 2)

    def test_soft_delete_goal_log(self):
        from atelier.models import GoalLog
        log = GoalLog.objects.create(project=self.project, user=self.user, body='To delete')
        resp = self.client.delete(self._log_url(log.id))
        self.assertEqual(resp.status_code, 204)
        log.refresh_from_db()
        self.assertTrue(log.is_deleted)

    def test_deleted_log_not_in_list(self):
        from atelier.models import GoalLog
        log = GoalLog.objects.create(project=self.project, user=self.user, body='Hidden', is_deleted=True)
        resp = self.client.get(self._logs_url())
        ids = [l['id'] for l in resp.json()['logs']]
        self.assertNotIn(log.id, ids)

    def test_toggle_done(self):
        from atelier.models import GoalLog
        log = GoalLog.objects.create(project=self.project, user=self.user, body='Mark done')
        resp = self.client.patch(
            self._log_url(log.id),
            data=json.dumps({'is_done': True}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['is_done'])

    def test_other_user_cannot_access_logs(self):
        from atelier.models import Project, GoalLog
        other = make_user('other_goal')
        other_proj = Project.objects.create(user=other, title='Other Goal')
        GoalLog.objects.create(project=other_proj, user=other, body='private')
        resp = self.client.get(reverse('atelier:api_goal_logs_list', args=[other_proj.id]))
        self.assertEqual(resp.status_code, 404)

    def test_default_log_type_is_note(self):
        resp = self.client.post(
            self._logs_url(),
            data=json.dumps({'body': 'Just a note'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['log_type'], 'note')

    def test_project_api_includes_goal_description(self):
        resp = self.client.get(reverse('atelier:api_project_detail', args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('goal_description', data)
        self.assertNotIn('current_focus', data)
        self.assertNotIn('next_steps', data)

