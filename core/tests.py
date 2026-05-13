from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import PageScene, SceneLayer


class SceneLayerModelTests(TestCase):
    def setUp(self):
        self.scene = PageScene.objects.create(name='Scene A', is_active=True, viewport_mode='both')

    def test_layer_tier_is_forced_by_layer_type(self):
        layer = SceneLayer.objects.create(
            scene=self.scene,
            layer_type='text',
            layer_tier=-3,
            z_index=10,
            x=0,
            y=0,
            width=100,
            height=40,
            settings_json={'text': 'hello'},
        )
        self.assertEqual(layer.layer_tier, 1)

    def test_sticker_z_index_range(self):
        with self.assertRaises(ValidationError):
            layer = SceneLayer(
                scene=self.scene,
                layer_type='sticker',
                layer_tier=2,
                z_index=1000,
                x=10,
                y=10,
                width=100,
                height=100,
            )
            layer.full_clean()


class SceneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.scene = PageScene.objects.create(name='Main Scene', is_active=True)
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username='admin',
            password='pass1234',
            email='admin@example.com',
            nickname='adminnick',
        )

    def test_active_scene_endpoint(self):
        SceneLayer.objects.create(
            scene=self.scene,
            layer_type='text',
            layer_tier=1,
            z_index=2,
            x=10,
            y=12,
            width=200,
            height=60,
            settings_json={'text': 'Mission Control'},
        )
        response = self.client.get('/api/mainpage/scene/active')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['data']['id'], self.scene.id)
        self.assertEqual(len(body['data']['layers']), 1)

    def test_layer_create_requires_admin(self):
        response = self.client.post('/api/editor/layers', {'scene_id': self.scene.id, 'layer_type': 'text'}, format='json')
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/editor/layers', {
            'scene_id': self.scene.id,
            'layer_type': 'sticker',
            'x': 20,
            'y': 20,
            'width': 120,
            'height': 120,
            'z_index': 500,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['data']['layer_tier'], 2)

    def test_layer_patch_rejects_invalid_tier_change(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/editor/layers', {
            'scene_id': self.scene.id,
            'layer_type': 'sticker',
            'z_index': 10,
            'x': 20,
            'y': 20,
            'width': 120,
            'height': 120,
        }, format='json')
        layer_id = response.json()['data']['id']

        patch = self.client.patch(f'/api/editor/layers/{layer_id}', {'layer_tier': 1}, format='json')
        self.assertEqual(patch.status_code, 400)

    def test_revision_restore_flow(self):
        self.client.force_authenticate(user=self.admin)
        create = self.client.post('/api/editor/layers', {
            'scene_id': self.scene.id,
            'layer_type': 'text',
            'x': 10,
            'y': 20,
            'width': 200,
            'height': 40,
            'z_index': 0,
            'settings_json': {'text': 'A'},
        }, format='json')
        self.assertEqual(create.status_code, 201)

        rev = self.client.post('/api/editor/revisions', {'scene_id': self.scene.id}, format='json')
        self.assertEqual(rev.status_code, 200)
        rev_id = rev.json()['data']['id']

        layer_id = create.json()['data']['id']
        self.client.delete(f'/api/editor/layers/{layer_id}/delete')
        self.assertEqual(SceneLayer.objects.filter(scene=self.scene).count(), 0)

        restore = self.client.post(f'/api/editor/revisions/{rev_id}/restore', {}, format='json')
        self.assertEqual(restore.status_code, 200)
        self.assertEqual(SceneLayer.objects.filter(scene=self.scene).count(), 1)
