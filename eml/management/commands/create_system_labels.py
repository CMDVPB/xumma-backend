from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from ayy.models import MailLabelV2


SYSTEM_LABELS = [
    ("inbox", "Inbox", 1),
    ("sent", "Sent", 2),
    ("drafts", "Drafts", 3),
    ("trash", "Trash", 99),
]


class Command(BaseCommand):
    help = "Create system mail labels for existing users"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        created = 0

        for user in User.objects.all():
            for slug, name, order in SYSTEM_LABELS:
                _, was_created = MailLabelV2.objects.get_or_create(
                    user=user,
                    slug=slug,
                    defaults={
                        "name": name,
                        "type": MailLabelV2.SYSTEM,
                        "order": order,
                    },
                )
                if was_created:
                    created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"System labels ensured. Created {created} labels.")
        )
