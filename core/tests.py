import io
import struct
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from .models import CustomFont, PageScene, SceneLayer
from .views import validate_file_magic_bytes


# ─────────────────────────────────────────────────────────────
# Model tests
# ─────────────────────────────────────────────────────────────

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

    def test_all_layer_types_have_correct_tier(self):
        expected = {
            'bg_image': -3,
            'parallax_far': -2,
            'bg_text': -1,
            'main_image': 0,
            'text': 1,
            'clock': 1,
            'menu_button': 1,
            'user_profile': 1,
            'sticker': 2,
            'parallax_near': 3,
            'parallax_ultra_near': 4,
        }
        for layer_type, tier in expected.items():
            with self.subTest(layer_type=layer_type):
                self.assertEqual(SceneLayer.TYPE_TIER_MAP[layer_type], tier)

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

    def test_sticker_z_index_minimum_boundary(self):
        """z_index=0 is valid for stickers."""
        layer = SceneLayer.objects.create(
            scene=self.scene,
            layer_type='sticker',
            layer_tier=2,
            z_index=0,
            x=10,
            y=10,
            width=80,
            height=80,
        )
        self.assertEqual(layer.z_index, 0)

    def test_sticker_z_index_maximum_boundary(self):
        """z_index=999 is valid for stickers."""
        layer = SceneLayer.objects.create(
            scene=self.scene,
            layer_type='sticker',
            layer_tier=2,
            z_index=999,
            x=10,
            y=10,
            width=80,
            height=80,
        )
        self.assertEqual(layer.z_index, 999)

    def test_layer_sort_order(self):
        """Layers must sort tier ASC → z_index ASC → id ASC."""
        a = SceneLayer.objects.create(scene=self.scene, layer_type='text', layer_tier=1, z_index=5, x=0, y=0, width=100, height=40)
        b = SceneLayer.objects.create(scene=self.scene, layer_type='sticker', layer_tier=2, z_index=0, x=0, y=0, width=80, height=80)
        c = SceneLayer.objects.create(scene=self.scene, layer_type='text', layer_tier=1, z_index=1, x=0, y=0, width=100, height=40)
        d = SceneLayer.objects.create(scene=self.scene, layer_type='bg_image', layer_tier=-3, z_index=0, x=0, y=0, width=1920, height=1080)
        e = SceneLayer.objects.create(scene=self.scene, layer_type='text', layer_tier=1, z_index=1, x=0, y=0, width=100, height=40)

        ordered = list(SceneLayer.objects.filter(scene=self.scene).order_by('layer_tier', 'z_index', 'id'))
        self.assertEqual(ordered[0], d)  # tier=-3
        self.assertEqual(ordered[1], c)  # tier=1, z=1, lower id
        self.assertEqual(ordered[2], e)  # tier=1, z=1, higher id
        self.assertEqual(ordered[3], a)  # tier=1, z=5
        self.assertEqual(ordered[4], b)  # tier=2

    def test_invalid_layer_type_rejected(self):
        with self.assertRaises((ValidationError, KeyError)):
            layer = SceneLayer(
                scene=self.scene,
                layer_type='nonexistent_type',
                layer_tier=0,
                z_index=0,
                x=0,
                y=0,
                width=100,
                height=100,
            )
            layer.save()

    def test_coordinate_rotation_stored(self):
        layer = SceneLayer.objects.create(
            scene=self.scene,
            layer_type='main_image',
            layer_tier=0,
            z_index=0,
            x=120.5,
            y=300.0,
            width=640,
            height=480,
            rotation_deg=45.0,
            scale=1.5,
            opacity=0.8,
        )
        layer.refresh_from_db()
        self.assertAlmostEqual(layer.x, 120.5)
        self.assertAlmostEqual(layer.y, 300.0)
        self.assertAlmostEqual(layer.rotation_deg, 45.0)
        self.assertAlmostEqual(layer.scale, 1.5)
        self.assertAlmostEqual(layer.opacity, 0.8)


# ─────────────────────────────────────────────────────────────
# Upload / magic-bytes validation tests
# ─────────────────────────────────────────────────────────────

def _make_jpeg_bytes():
    buf = io.BytesIO()
    from PIL import Image as PILImage
    img = PILImage.new('RGB', (4, 4), color=(200, 100, 50))
    img.save(buf, format='JPEG')
    return buf.getvalue()


def _make_png_bytes():
    buf = io.BytesIO()
    from PIL import Image as PILImage
    img = PILImage.new('RGB', (4, 4), color=(50, 100, 200))
    img.save(buf, format='PNG')
    return buf.getvalue()


class MagicBytesValidationTests(TestCase):
    def test_valid_jpeg(self):
        validate_file_magic_bytes(_make_jpeg_bytes(), 'test.jpg', 'image/jpeg')

    def test_valid_png(self):
        validate_file_magic_bytes(_make_png_bytes(), 'test.png', 'image/png')

    def test_invalid_bytes_rejected(self):
        fake = b'not-an-image-header-at-all' + b'\x00' * 20
        with self.assertRaises(ValueError):
            validate_file_magic_bytes(fake, 'evil.jpg', 'image/jpeg')

    def test_truncated_data_rejected(self):
        with self.assertRaises(ValueError):
            validate_file_magic_bytes(b'\x00\x01', 'tiny.jpg', 'image/jpeg')


# ─────────────────────────────────────────────────────────────
# API tests
# ─────────────────────────────────────────────────────────────

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

    def test_healthz(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)

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

    def test_active_scene_layers_sorted_correctly(self):
        """Active scene layers arrive sorted by tier→z_index→id."""
        SceneLayer.objects.create(scene=self.scene, layer_type='sticker', layer_tier=2, z_index=1, x=0, y=0, width=80, height=80)
        SceneLayer.objects.create(scene=self.scene, layer_type='text', layer_tier=1, z_index=5, x=0, y=0, width=100, height=40)
        SceneLayer.objects.create(scene=self.scene, layer_type='bg_image', layer_tier=-3, z_index=0, x=0, y=0, width=1920, height=1080)

        body = self.client.get('/api/mainpage/scene/active').json()
        tiers = [l['layer_tier'] for l in body['data']['layers']]
        self.assertEqual(tiers, sorted(tiers))

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

    def test_layer_create_invalid_type_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/editor/layers', {
            'scene_id': self.scene.id,
            'layer_type': 'bogus_type',
            'x': 0, 'y': 0, 'width': 100, 'height': 100,
        }, format='json')
        self.assertEqual(response.status_code, 400)

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

    def test_sticker_z_index_out_of_range_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/editor/layers', {
            'scene_id': self.scene.id,
            'layer_type': 'sticker',
            'x': 20, 'y': 20, 'width': 80, 'height': 80,
            'z_index': 1000,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_delete_layer_returns_404_for_missing(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete('/api/editor/layers/99999/delete')
        self.assertEqual(response.status_code, 404)

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

    def test_current_user_profile_requires_authentication(self):
        response = self.client.get('/api/user/profile/')
        self.assertIn(response.status_code, (401, 403))

    def test_current_user_profile_returns_current_user_data(self):
        self.client.force_authenticate(user=self.admin)
        self.admin.points = 1234
        self.admin.save(update_fields=['points'])

        response = self.client.get('/api/user/profile/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['data']['nickname'], self.admin.nickname)
        self.assertEqual(body['data']['points'], 1234)
        self.assertIsNone(body['data']['profile_image_url'])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class FontApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username='fontadmin',
            password='pass1234',
            email='fontadmin@example.com',
            nickname='fontadmin',
        )
        self.client.force_authenticate(user=self.admin)

    def test_register_font_url_and_list_fonts(self):
        response = self.client.post(
            '/api/editor/fonts/register-url',
            {'name': 'Pretendard CDN', 'font_family': 'Pretendard', 'url': 'https://example.com/font.woff2'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CustomFont.objects.count(), 1)

        listing = self.client.get('/api/editor/fonts/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['data'][0]['font_family'], 'Pretendard')
        self.assertEqual(listing.json()['data'][0]['url'], 'https://example.com/font.woff2')

    def test_upload_font_and_delete_font(self):
        upload = SimpleUploadedFile('sample.woff2', b'font-bytes', content_type='font/woff2')
        response = self.client.post(
            '/api/editor/fonts/upload',
            {'name': 'Uploaded Font', 'font_family': 'UploadedFamily', 'file': upload},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        font = CustomFont.objects.get(name='Uploaded Font')
        self.assertTrue(font.file_path.endswith('.woff2'))
        self.assertEqual(font.format, 'woff2')

        delete = self.client.delete(f'/api/editor/fonts/{font.id}/delete')
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(CustomFont.objects.filter(id=font.id).exists())

    def test_upload_font_rejects_invalid_extension(self):
        upload = SimpleUploadedFile('sample.txt', b'font-bytes', content_type='text/plain')
        response = self.client.post(
            '/api/editor/fonts/upload',
            {'name': 'Bad Font', 'font_family': 'BadFamily', 'file': upload},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CustomFont.objects.count(), 0)


class UploadValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username='admin2',
            password='pass1234',
            email='admin2@example.com',
            nickname='adminnick2',
        )
        self.client.force_authenticate(user=self.admin)

    def test_upload_valid_jpeg(self):
        buf = io.BytesIO(_make_jpeg_bytes())
        buf.name = 'photo.jpg'
        response = self.client.post(
            '/api/assets/upload',
            {'file': buf, 'kind': 'generic'},
            format='multipart',
        )
        self.assertIn(response.status_code, (200, 201))
        self.assertTrue(response.json().get('ok'))

    def test_upload_invalid_format_rejected(self):
        buf = io.BytesIO(b'this is definitely not an image')
        buf.name = 'fake.jpg'
        response = self.client.post(
            '/api/assets/upload',
            {'file': buf, 'kind': 'generic'},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get('ok'))
        self.assertEqual(response.json().get('error_code'), 'UNSUPPORTED_FORMAT')

    def test_upload_requires_admin(self):
        anon_client = APIClient()
        buf = io.BytesIO(_make_jpeg_bytes())
        buf.name = 'photo.jpg'
        response = anon_client.post(
            '/api/assets/upload',
            {'file': buf, 'kind': 'generic'},
            format='multipart',
        )
        self.assertEqual(response.status_code, 403)
