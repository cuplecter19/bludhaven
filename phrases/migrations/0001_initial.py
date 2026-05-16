import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('leitner', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('name_ko', models.CharField(max_length=100)),
                ('color_hex', models.CharField(default='#c8a96e', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='PhraseCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sentence_en', models.TextField()),
                ('sentence_ko', models.TextField()),
                ('phrase', models.CharField(max_length=150)),
                ('phrase_ko', models.CharField(max_length=200)),
                ('example_source', models.CharField(blank=True, max_length=200, null=True)),
                ('difficulty', models.SmallIntegerField(default=1)),
                ('box_number', models.SmallIntegerField(default=1)),
                ('next_review_at', models.DateField(default=django.utils.timezone.localdate)),
                ('last_reviewed_at', models.DateField(blank=True, null=True)),
                ('review_count', models.IntegerField(default=0)),
                ('correct_streak', models.SmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('memo', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phrase_cards', to=settings.AUTH_USER_MODEL)),
                ('source_word', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='phrase_cards', to='leitner.wordsense')),
                ('tags', models.ManyToManyField(blank=True, related_name='phrase_cards', to='phrases.tag')),
            ],
        ),
        migrations.AddIndex(
            model_name='phrasecard',
            index=models.Index(
                condition=models.Q(is_active=True),
                fields=['user', 'next_review_at', 'box_number'],
                name='phrases_card_review_idx',
            ),
        ),
        migrations.CreateModel(
            name='ReviewLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('cloze', 'Cloze'), ('scramble', 'Scramble')], max_length=10)),
                ('result', models.CharField(choices=[('again', 'Again'), ('hard', 'Hard'), ('good', 'Good'), ('easy', 'Easy')], max_length=10)),
                ('box_before', models.SmallIntegerField()),
                ('box_after', models.SmallIntegerField()),
                ('response_ms', models.IntegerField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phrase_review_logs', to=settings.AUTH_USER_MODEL)),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_logs', to='phrases.phrasecard')),
            ],
        ),
        migrations.AddIndex(
            model_name='reviewlog',
            index=models.Index(fields=['user', '-reviewed_at'], name='phrases_rlog_user_idx'),
        ),
        migrations.AddIndex(
            model_name='reviewlog',
            index=models.Index(fields=['card', '-reviewed_at'], name='phrases_rlog_card_idx'),
        ),
        migrations.CreateModel(
            name='ScrambleAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submitted_order', models.TextField()),
                ('correct_order', models.TextField()),
                ('is_correct', models.BooleanField()),
                ('attempt_number', models.SmallIntegerField()),
                ('time_taken_ms', models.IntegerField(blank=True, null=True)),
                ('attempted_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scramble_attempts', to=settings.AUTH_USER_MODEL)),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scramble_attempts', to='phrases.phrasecard')),
            ],
        ),
        migrations.AddIndex(
            model_name='scrambleattempt',
            index=models.Index(fields=['user', '-attempted_at'], name='phrases_sattempt_idx'),
        ),
        migrations.CreateModel(
            name='DailySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('cloze_reviewed', models.IntegerField(default=0)),
                ('cloze_correct', models.IntegerField(default=0)),
                ('scramble_attempted', models.IntegerField(default=0)),
                ('scramble_correct', models.IntegerField(default=0)),
                ('new_cards_added', models.IntegerField(default=0)),
                ('study_duration_sec', models.IntegerField(default=0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phrase_daily_summaries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'date')},
            },
        ),
        migrations.AddIndex(
            model_name='dailysummary',
            index=models.Index(fields=['user', 'date'], name='phrases_dsummary_idx'),
        ),
    ]
