import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from voting.models import Election, Candidate

class Command(BaseCommand):
    help = "Migrates uploaded media files to the static directory and updates database records to make them persistent."

    def handle(self, *args, **options):
        # Ensure target static directories exist
        static_photos_dir = os.path.join(settings.BASE_DIR, "voting", "static", "voting", "photos")
        static_symbols_dir = os.path.join(settings.BASE_DIR, "voting", "static", "voting", "symbols")
        os.makedirs(static_photos_dir, exist_ok=True)
        os.makedirs(static_symbols_dir, exist_ok=True)

        # Helper to migrate a file
        def migrate_file(field_file, target_dir, prefix):
            if not field_file:
                return None
            name = field_file.name
            # If it already starts with voting/, it's already a static reference
            if name.startswith("voting/"):
                return name
            
            try:
                src_path = field_file.path
            except NotImplementedError:
                self.stdout.write(self.style.WARNING(f"Field {name} is not stored locally."))
                return None

            if not os.path.exists(src_path):
                self.stdout.write(self.style.WARNING(f"File not found on local disk: {src_path}"))
                return None
            
            filename = os.path.basename(name)
            dst_path = os.path.join(target_dir, filename)
            shutil.copy2(src_path, dst_path)
            self.stdout.write(self.style.SUCCESS(f"Copied {filename} to static {prefix}/"))
            return f"voting/{prefix}/{filename}"

        # Migrate Elections
        for election in Election.objects.all():
            if election.logo and not election.logo.name.startswith("voting/"):
                new_path = migrate_file(election.logo, static_photos_dir, "photos")
                if new_path:
                    election.logo = new_path
                    election.save()

        # Migrate Candidates
        for cand in Candidate.objects.all():
            if cand.photo and not cand.photo.name.startswith("voting/"):
                new_path = migrate_file(cand.photo, static_photos_dir, "photos")
                if new_path:
                    cand.photo = new_path
                    cand.save()
            if cand.symbol and not cand.symbol.name.startswith("voting/"):
                new_path = migrate_file(cand.symbol, static_symbols_dir, "symbols")
                if new_path:
                    cand.symbol = new_path
                    cand.save()

        self.stdout.write(self.style.SUCCESS("Successfully migrated all uploaded media assets to static files!"))
