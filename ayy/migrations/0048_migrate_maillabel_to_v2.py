from django.db import migrations


def migrate_labels(apps, schema_editor):
    Old = apps.get_model("ayy", "MailLabel")
    New = apps.get_model("ayy", "MailLabelV2")

    for label in Old.objects.all():
        New.objects.get_or_create(
            user=label.user,
            slug=label.id,
            defaults={
                "name": label.name,
                "type": label.type,
                "order": label.order,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("ayy", "0047_maillabelv2"),
    ]

    operations = [
        migrations.RunPython(migrate_labels),
    ]
