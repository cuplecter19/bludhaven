from django.db import migrations

INITIAL_SPARK_TAGS = [
    ('idea', '아이디어', 1),
    ('thought', '생각', 2),
    ('discovery', '발견', 3),
    ('question', '질문', 4),
    ('other', '기타', 5),
]


def create_initial_tags(apps, schema_editor):
    SparkTag = apps.get_model('atelier', 'SparkTag')
    for name, name_ko, sort_order in INITIAL_SPARK_TAGS:
        SparkTag.objects.get_or_create(
            name=name,
            defaults={'name_ko': name_ko, 'sort_order': sort_order},
        )


def delete_initial_tags(apps, schema_editor):
    SparkTag = apps.get_model('atelier', 'SparkTag')
    SparkTag.objects.filter(name__in=[t[0] for t in INITIAL_SPARK_TAGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('atelier', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_tags, delete_initial_tags),
    ]
