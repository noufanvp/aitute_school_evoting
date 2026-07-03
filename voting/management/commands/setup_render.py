import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from voting.models import Election
from voting.management.commands.seed_election import Command as SeedElectionCommand

class Command(BaseCommand):
    help = "Runs initial database setup for Render: creates default users and seeds sample data if empty."

    def handle(self, *args, **options):
        User = get_user_model()

        # Auto-create cache table if DatabaseCache is used in current settings
        try:
            self.stdout.write("Checking/creating database cache table...")
            call_command("createcachetable")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not create cache table (might not be using DatabaseCache): {e}"))

        # Admin superuser
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(username="admin", password="admin123")
            self.stdout.write(self.style.SUCCESS("Created superuser: admin"))
        else:
            user = User.objects.get(username="admin")
            user.set_password("admin123")
            user.save()
            self.stdout.write("Updated password for user: admin")

        # Invigilator user
        if not User.objects.filter(username="invigilator").exists():
            User.objects.create_user(username="invigilator", password="MicesInvigilator2026", is_staff=False, is_superuser=False)
            self.stdout.write(self.style.SUCCESS("Created user: invigilator"))
        else:
            user = User.objects.get(username="invigilator")
            user.set_password("MicesInvigilator2026")
            user.save()
            self.stdout.write("Updated password for user: invigilator")

        # Test user
        if not User.objects.filter(username="testuser").exists():
            User.objects.create_user(username="testuser", password="MicesTest2026", is_staff=False, is_superuser=False)
            self.stdout.write(self.style.SUCCESS("Created user: testuser"))
        else:
            user = User.objects.get(username="testuser")
            user.set_password("MicesTest2026")
            user.save()
            self.stdout.write("Updated password for user: testuser")

        # micestest user
        if not User.objects.filter(username="micestest").exists():
            User.objects.create_user(username="micestest", password="MicesTest2026", is_staff=False, is_superuser=False)
            self.stdout.write(self.style.SUCCESS("Created user: micestest"))
        else:
            user = User.objects.get(username="micestest")
            user.set_password("MicesTest2026")
            user.save()
            self.stdout.write("Updated password for user: micestest")

        # Seeding logic: check for Mices and NEMS elections individually.
        # This allows us to auto-seed NEMS on the next redeploy even if Mices already exists.
        mices_exists = Election.objects.filter(school_name="Mices Public School").exists()
        nems_exists = Election.objects.filter(school_name="Narikkuni English Medium School").exists()
        
        force_seed = os.environ.get("FORCE_SEED", "False") == "True"

        # Check for legacy formats (only relevant if Mices exists)
        has_legacy_formats = False
        if mices_exists:
            from voting.models import Candidate
            has_legacy_formats = (
                Candidate.objects.filter(photo__endswith='.jpg').exists() or
                Candidate.objects.filter(photo__endswith='.png').exists() or
                Candidate.objects.filter(symbol__endswith='.jpg').exists() or
                Candidate.objects.filter(symbol__endswith='.png').exists()
            )

        # Check if NEMS has any dynamic uploaded media (does not start with voting/)
        nems_has_uploads = False
        if nems_exists:
            from voting.models import Candidate
            nems_has_uploads = Candidate.objects.filter(
                position__election__school_name="Narikkuni English Medium School"
            ).exclude(photo__startswith="voting/").exists()

        # Seeding command
        seed_cmd = SeedElectionCommand()

        # Seed Mices if it doesn't exist, has legacy formats, or if forced
        if force_seed or not mices_exists or has_legacy_formats:
            self.stdout.write("Mices Public School election not found, has legacy formats, or FORCE_SEED active. Seeding Mices...")
            seed_cmd.handle(title="Student Council Election 2026-27", school="Mices Public School")
            self.stdout.write(self.style.SUCCESS("Mices Public School election seeded successfully."))
        else:
            self.stdout.write("Mices Public School election already exists. Skipping Mices seeding.")

        # Seed NEMS if it doesn't exist, if it contains dynamic media uploads, or if forced
        if force_seed or not nems_exists or nems_has_uploads:
            self.stdout.write("Narikkuni English Medium School election not found, has dynamic uploads, or FORCE_SEED active. Seeding NEMS...")
            seed_cmd.handle(title="Student Council Election 2026-27", school="Narikkuni English Medium School")
            self.stdout.write(self.style.SUCCESS("Narikkuni English Medium School election seeded successfully."))
        else:
            self.stdout.write("Narikkuni English Medium School election already exists. Skipping NEMS seeding.")
