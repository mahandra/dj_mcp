from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

SEED_USERS = [
    ("alice", "Alice", "Morgan", date(1990, 3, 14), "Tampa", "Bayshore Software"),
    ("bob", "Bob", "Nguyen", date(1985, 7, 2), "Orlando", "Sunrail Logistics"),
    ("carol", "Carol", "Diaz", date(1993, 11, 21), "Miami", "Coral Health"),
    ("david", "David", "Kim", date(1978, 1, 30), "Atlanta", "Peachtree Bank"),
    ("emma", "Emma", "Rossi", date(1998, 5, 9), "Chicago", "Lakeshore Media"),
    ("frank", "Frank", "Olsen", date(1982, 9, 17), "Denver", "Summit Energy"),
    ("grace", "Grace", "Patel", date(1995, 12, 3), "Seattle", "Rainier Cloud"),
    ("henry", "Henry", "Brown", date(1970, 6, 25), "Boston", "Harbor University"),
    ("irene", "Irene", "Costa", date(1988, 2, 11), "Austin", "Lonestar Robotics"),
    ("jack", "Jack", "Wilson", date(2000, 8, 28), "Portland", "Rosewood Design"),
]


class Command(BaseCommand):
    help = "Create demo users with profiles. Existing usernames are left untouched."

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for username, first_name, last_name, birth_date, city, workplace in SEED_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@example.com",
                },
            )
            if not created:
                continue
            user.set_unusable_password()
            user.save(update_fields=["password"])
            user.profile.birth_date = birth_date
            user.profile.city = city
            user.profile.workplace = workplace
            user.profile.save()
            created_count += 1

        skipped = len(SEED_USERS) - created_count
        self.stdout.write(
            self.style.SUCCESS(f"Created {created_count} users, skipped {skipped}.")
        )
