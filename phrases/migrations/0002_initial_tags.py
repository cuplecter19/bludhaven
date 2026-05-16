from django.db import migrations

INITIAL_TAGS = [
    ('phrasal_verb', '구동사', '#4a90d9'),
    ('idiom', '관용어', '#e07b39'),
    ('preposition', '전치사구', '#7cb87f'),
    ('grammar', '문법 표현', '#9b59b6'),
    ('collocation', '연어', '#c8a96e'),
]


def create_initial_tags(apps, schema_editor):
    Tag = apps.get_model('phrases', 'Tag')
    for name, name_ko, color_hex in INITIAL_TAGS:
        Tag.objects.get_or_create(
            name=name,
            defaults={'name_ko': name_ko, 'color_hex': color_hex},
        )


def delete_initial_tags(apps, schema_editor):
    Tag = apps.get_model('phrases', 'Tag')
    Tag.objects.filter(name__in=[t[0] for t in INITIAL_TAGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('phrases', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_tags, delete_initial_tags),
    ]
