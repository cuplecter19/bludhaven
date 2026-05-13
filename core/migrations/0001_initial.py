from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MediaAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('background', 'Background'), ('main', 'Main'), ('parallax', 'Parallax'), ('sticker', 'Sticker'), ('generic', 'Generic')], default='generic', max_length=30)),
                ('mime_type', models.CharField(max_length=100)),
                ('storage_path', models.CharField(max_length=400)),
                ('width', models.PositiveIntegerField()),
                ('height', models.PositiveIntegerField()),
                ('bytes', models.BigIntegerField()),
                ('hash_sha256', models.CharField(max_length=64)),
                ('original_deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='PageScene',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=False)),
                ('viewport_mode', models.CharField(choices=[('desktop', 'Desktop'), ('mobile', 'Mobile'), ('both', 'Both')], default='both', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-is_active', 'id']},
        ),
        migrations.CreateModel(
            name='SceneLayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('layer_type', models.CharField(choices=[('bg_image', 'Background Image'), ('parallax_far', 'Parallax Far'), ('bg_text', 'Background Text'), ('main_image', 'Main Image'), ('text', 'Text'), ('clock', 'Clock'), ('menu_button', 'Menu Button'), ('sticker', 'Sticker'), ('parallax_near', 'Parallax Near'), ('parallax_ultra_near', 'Parallax Ultra Near')], max_length=40)),
                ('layer_tier', models.IntegerField()),
                ('z_index', models.PositiveIntegerField(default=0)),
                ('enabled', models.BooleanField(default=True)),
                ('x', models.FloatField(default=0)),
                ('y', models.FloatField(default=0)),
                ('width', models.FloatField(default=200)),
                ('height', models.FloatField(default=200)),
                ('rotation_deg', models.FloatField(default=0)),
                ('scale', models.FloatField(default=1)),
                ('opacity', models.FloatField(default=1)),
                ('settings_json', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scene', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='layers', to='core.pagescene')),
            ],
            options={'ordering': ['layer_tier', 'z_index', 'id']},
        ),
        migrations.CreateModel(
            name='EditorRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('snapshot_json', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('scene', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='core.pagescene')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
