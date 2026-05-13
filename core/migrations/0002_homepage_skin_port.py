from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # IndexImage: sticker layer choice 추가 및 배치 필드 추가
        migrations.AlterField(
            model_name='indeximage',
            name='layer',
            field=models.CharField(
                choices=[
                    ('background', 'Background (Parallax)'),
                    ('main', 'Main'),
                    ('sticker', 'Sticker'),
                ],
                default='main',
                max_length=20,
            ),
        ),
        migrations.AlterModelOptions(
            name='indeximage',
            options={'ordering': ['layer', 'order', 'z_index']},
        ),
        migrations.AddField(
            model_name='indeximage',
            name='pos_left',
            field=models.CharField(default='50%', max_length=20),
        ),
        migrations.AddField(
            model_name='indeximage',
            name='pos_top',
            field=models.CharField(default='50%', max_length=20),
        ),
        migrations.AddField(
            model_name='indeximage',
            name='width',
            field=models.CharField(default='160px', max_length=20),
        ),
        migrations.AddField(
            model_name='indeximage',
            name='height',
            field=models.CharField(default='auto', max_length=20),
        ),
        migrations.AddField(
            model_name='indeximage',
            name='rotate',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='indeximage',
            name='z_index',
            field=models.PositiveIntegerField(default=10),
        ),
        # TextBlock: unique 제약 제거 및 배치 필드 추가
        migrations.AlterField(
            model_name='textblock',
            name='position',
            field=models.CharField(
                choices=[
                    ('bg_text', 'Background Text'),
                    ('block1', 'Text Block 1'),
                    ('block2', 'Text Block 2'),
                    ('block3', 'Text Block 3'),
                ],
                default='block1',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='textblock',
            name='pos_left',
            field=models.CharField(default='5%', max_length=20),
        ),
        migrations.AddField(
            model_name='textblock',
            name='pos_top',
            field=models.CharField(default='5%', max_length=20),
        ),
        migrations.AddField(
            model_name='textblock',
            name='font_size',
            field=models.CharField(default='1rem', max_length=20),
        ),
        migrations.AddField(
            model_name='textblock',
            name='color',
            field=models.CharField(default='#ffffff', max_length=20),
        ),
        migrations.AddField(
            model_name='textblock',
            name='z_index',
            field=models.PositiveIntegerField(default=20),
        ),
        # 신규 모델: ParallaxConfig
        migrations.CreateModel(
            name='ParallaxConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('speed', models.FloatField(default=0.4)),
                ('blur_px', models.IntegerField(default=0)),
                ('overlay_opacity', models.FloatField(default=0.3)),
            ],
            options={
                'verbose_name': 'Parallax Config',
            },
        ),
        # 신규 모델: ClockWidgetConfig
        migrations.CreateModel(
            name='ClockWidgetConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('pos_left', models.CharField(default='2%', max_length=20)),
                ('pos_top', models.CharField(default='2%', max_length=20)),
                ('font_size', models.CharField(default='1rem', max_length=20)),
                ('color', models.CharField(default='#ffffff', max_length=20)),
                ('z_index', models.PositiveIntegerField(default=30)),
            ],
            options={
                'verbose_name': 'Clock Widget Config',
            },
        ),
    ]
