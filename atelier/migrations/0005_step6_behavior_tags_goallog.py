import datetime

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def merge_focus_and_steps(apps, schema_editor):
    """Copy current_focus + next_steps into goal_description."""
    Project = apps.get_model('atelier', 'Project')
    for project in Project.objects.all():
        parts = []
        if project.current_focus:
            parts.append(project.current_focus)
        if project.next_steps:
            parts.append(project.next_steps)
        project.goal_description = '\n'.join(parts)
        project.save(update_fields=['goal_description'])


class Migration(migrations.Migration):

    dependencies = [
        ('atelier', '0004_add_completed_notes_to_project'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add behavior_tags to MoodLog
        migrations.AddField(
            model_name='moodlog',
            name='behavior_tags',
            field=models.CharField(blank=True, default='', max_length=200),
        ),

        # 2. Add goal_description to Project (nullable first for data migration)
        migrations.AddField(
            model_name='project',
            name='goal_description',
            field=models.TextField(blank=True, null=True),
        ),

        # 3. Migrate data from current_focus + next_steps → goal_description
        migrations.RunPython(merge_focus_and_steps, migrations.RunPython.noop),

        # 4. Remove current_focus
        migrations.RemoveField(
            model_name='project',
            name='current_focus',
        ),

        # 5. Remove next_steps
        migrations.RemoveField(
            model_name='project',
            name='next_steps',
        ),

        # 6. Make goal_description NOT NULL DEFAULT ''
        migrations.AlterField(
            model_name='project',
            name='goal_description',
            field=models.TextField(blank=True, default=''),
        ),

        # 7. Create GoalLog table
        migrations.CreateModel(
            name='GoalLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('body', models.TextField()),
                ('is_done', models.BooleanField(default=False)),
                ('log_type', models.CharField(
                    choices=[('note', 'Note'), ('done', 'Done'), ('next', 'Next')],
                    default='note',
                    max_length=20,
                )),
                ('logged_at', models.DateField(default=datetime.date.today)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='goal_logs',
                    to='atelier.project',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='goal_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['project', '-logged_at'], name='atelier_glog_proj_idx'),
                    models.Index(fields=['user', '-logged_at'], name='atelier_glog_user_idx'),
                ],
            },
        ),
    ]
