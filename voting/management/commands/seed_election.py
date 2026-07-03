from django.core.management.base import BaseCommand
from django.utils import timezone

from voting.models import Candidate
from voting.models import Election
from voting.models import Position


SEED_DATA_MICES = [
    {
        "position": "HEAD BOY",
        "icon": "👑",
        "candidates": [
            {"name": "Muhammed Aiman Changana", "class_name": "N/A", "motto": "", "photo": "voting/photos/Muhammed_Aiman_Changana.webp", "symbol": "voting/symbols/symbol_globe.webp"},
            {"name": "Aman Muhammed", "class_name": "N/A", "motto": "", "photo": "voting/photos/Aman_Muhammed.webp", "symbol": "voting/symbols/symbol_car.webp"},
            {"name": "Muhammed Ayaan KT", "class_name": "N/A", "motto": "", "photo": "voting/photos/Muhammed_Ayaan_KT.webp", "symbol": "voting/symbols/symbol_tree.webp"},
        ],
    },
    {
        "position": "SPORTS CAPTAIN",
        "icon": "🌟",
        "candidates": [
            {"name": "Muhammed Hadi MP", "class_name": "N/A", "motto": "", "photo": "voting/photos/Muhammed_Hadi_MP.webp", "symbol": "voting/symbols/symbol_cricketBatAndBall.webp"},
            {"name": "Shahazin U", "class_name": "N/A", "motto": "", "photo": "voting/photos/Shahazin_U.webp", "symbol": "voting/symbols/symbol_football.webp"},
        ],
    },
    {
        "position": "FINE ARTS SECRETARY",
        "icon": "🎨",
        "candidates": [
            {"name": "Shada Fathima", "class_name": "N/A", "motto": "", "photo": "voting/photos/Shada_Fathima.webp", "symbol": "voting/symbols/symbol_camera.webp"},
            {"name": "Fathima Hadiya M", "class_name": "N/A", "motto": "", "photo": "voting/photos/Fathima_Hadiya_M.webp", "symbol": "voting/symbols/symbol_torch.webp"},
            {"name": "Ehan Muhammed TK", "class_name": "N/A", "motto": "", "photo": "voting/photos/Ehan_Muhammed_TK.webp", "symbol": "voting/symbols/symbol_autorickshaw.webp"},
            {"name": "Naban M", "class_name": "N/A", "motto": "", "photo": "voting/photos/Naban_M.webp", "symbol": "voting/symbols/symbol_jeep.webp"}
        ],
    },
    {
        "position": "MAGAZINE EDITOR",
        "icon": "📚",
        "candidates": [
            {"name": "Gayathri P", "class_name": "N/A", "motto": "", "photo": "voting/photos/Gayathiri_P.webp", "symbol": "voting/symbols/symbol_guitar.webp"},
            {"name": "Abdullah Nihal N", "class_name": "N/A", "motto": "", "photo": "voting/photos/Abdullah_Nihal_N.webp", "symbol": "voting/symbols/symbol_laptop.webp"},
            {"name": "Navaru Rahman", "class_name": "N/A", "motto": "", "photo": "voting/photos/Navaru_Rahman.webp", "symbol": "voting/symbols/symbol_pen.webp"},
            {"name": "Raiza Aysha MP", "class_name": "N/A", "motto": "", "photo": "voting/photos/Raiza_Aysha_P.webp", "symbol": "voting/symbols/symbol_star.webp"},
            {"name": "Azim Sadath P", "class_name": "N/A", "motto": "", "photo": "voting/photos/Azim_Sadath_P.webp", "symbol": "voting/symbols/symbol_bicycle.webp"}            
        ],
    },
    {
        "position": "HEAD PREFECT",
        "icon": "🏆",
        "candidates": [
            {"name": "Sheza Fathima K", "class_name": "N/A", "motto": "", "photo": "voting/photos/Sheza_Fathima_K.webp", "symbol": "voting/symbols/symbol_bulb.webp"},
            {"name": "Muhammed Yusuf", "class_name": "N/A", "motto": "", "photo": "voting/photos/Muhammed_Yusuf.webp", "symbol": "voting/symbols/symbol_bugle.webp"},
            {"name": "Haya Binth Shahrath", "class_name": "N/A", "motto": "", "photo": "voting/photos/Haya_Binth_Shahrath.webp", "symbol": "voting/symbols/symbol_pencil.webp"},
            {"name": "Dhaheen MP", "class_name": "N/A", "motto": "", "photo": "voting/photos/Dhaheen_MP.webp", "symbol": "voting/symbols/symbol_clock.webp"}            
        ],
    }
]

SEED_DATA_NEMS = [
    {
        "position": "HEAD BOY",
        "icon": "👑",
        "candidates": [
            {"name": "Muhammed Safwan", "class_name": "Class 10", "motto": "N/A", "photo": "voting/photos/Muhammed_Safwan.webp", "symbol": "voting/symbols/symbol_nems_computer.webp"},
            {"name": "Ishan Hafiz", "class_name": "Class 9", "motto": "N/A", "photo": "voting/photos/Ishan_Hafiz.webp", "symbol": "voting/symbols/symbol_nems_pen.webp"},
        ],
    },
    {
        "position": "HEAD GIRL",
        "icon": "👑",
        "candidates": [
            {"name": "Asiya Jaza K", "class_name": "Class 10", "motto": "N/A", "photo": "voting/photos/Asiya_Jaza_K.webp", "symbol": "voting/symbols/symbol_nems_bag.webp"},
            {"name": "Avani RS", "class_name": "Class 9", "motto": "N/A", "photo": "voting/photos/Avani_RS.webp", "symbol": "voting/symbols/symbol_nems_book.webp"},
        ],
    },
    {
        "position": "FINE ARTS",
        "icon": "🎨",
        "candidates": [
            {"name": "Jewel R Joshi", "class_name": "Class 10", "motto": "N/A", "photo": "voting/photos/Jewel_R_Joshi.webp", "symbol": "voting/symbols/symbol_nems_guitar.webp"},
            {"name": "Azzah Nazmin PP", "class_name": "Class 9", "motto": "N/A", "photo": "voting/photos/Azzah_Nazmin_PP.webp", "symbol": "voting/symbols/symbol_nems_drum.webp"},
        ],
    },
    {
        "position": "SPORTS CAPTAIN",
        "icon": "🌟",
        "candidates": [
            {"name": "Afeef Rahman", "class_name": "Class 10", "motto": "N/A", "photo": "voting/photos/Afeef_Rahman.webp", "symbol": "voting/symbols/symbol_nems_football.webp"},
            {"name": "Athif Muhammed", "class_name": "Class 9", "motto": "N/A", "photo": "voting/photos/Athif_Muhammed.webp", "symbol": "voting/symbols/symbol_nems_shuttle.webp"},
        ],
    }
]


class Command(BaseCommand):
    help = "Seed a sample school election with positions and candidates."

    def add_arguments(self, parser):
        parser.add_argument("--title", default="Student Council Election 2026-27")
        parser.add_argument("--school", default="Mices Public School")

    def handle(self, *args, **options):
        # Create default users if they don't exist
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Admin superuser
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(username="admin", password="admin123")
            self.stdout.write("Created superuser: admin")
        else:
            user = User.objects.get(username="admin")
            user.set_password("admin123")
            user.save()
            self.stdout.write("Updated password for user: admin")

        # Invigilator user
        if not User.objects.filter(username="invigilator").exists():
            User.objects.create_user(username="invigilator", password="MicesInvigilator2026", is_staff=False, is_superuser=False)
            self.stdout.write("Created user: invigilator")
        else:
            user = User.objects.get(username="invigilator")
            user.set_password("MicesInvigilator2026")
            user.save()
            self.stdout.write("Updated password for user: invigilator")

        # Test user
        if not User.objects.filter(username="testuser").exists():
            User.objects.create_user(username="testuser", password="MicesTest2026", is_staff=False, is_superuser=False)
            self.stdout.write("Created user: testuser")
        else:
            user = User.objects.get(username="testuser")
            user.set_password("MicesTest2026")
            user.save()
            self.stdout.write("Updated password for user: testuser")

        # micestest user
        if not User.objects.filter(username="micestest").exists():
            User.objects.create_user(username="micestest", password="MicesTest2026", is_staff=False, is_superuser=False)
            self.stdout.write("Created user: micestest")
        else:
            user = User.objects.get(username="micestest")
            user.set_password("MicesTest2026")
            user.save()
            self.stdout.write("Updated password for user: micestest")

        # Clean previous data for this specific election to avoid global resets
        from datetime import timedelta
        from voting.models import Vote, Ballot, Position, Candidate
        
        existing_election = Election.objects.filter(title=options["title"], school_name=options["school"]).first()
        if existing_election:
            self.stdout.write(f"Deleting existing election data for '{options['title']}' ({options['school']})...")
            # Cascade delete positions, candidates, ballots, and votes safely
            positions = existing_election.positions.all()
            Vote.objects.filter(position__in=positions).delete()
            Ballot.objects.filter(election=existing_election).delete()
            Candidate.objects.filter(position__in=positions).delete()
            positions.delete()
            existing_election.delete()

        # Select correct seed data and logo
        school_lower = options["school"].lower()
        logo_path = ""
        if "narikkuni" in school_lower or "nems" in school_lower:
            seed_data = SEED_DATA_NEMS
            logo_path = "voting/photos/nems.webp"
        else:
            seed_data = SEED_DATA_MICES

        election = Election.objects.create(
            title=options["title"],
            school_name=options["school"],
            status=Election.STATUS_OPEN,
            starts_at=timezone.now() - timedelta(hours=2),
            logo=logo_path,
        )

        for p_index, position_data in enumerate(seed_data):
            position = Position.objects.create(
                election=election,
                name=position_data["position"],
                icon=position_data["icon"],
                order=p_index,
            )
            for c_index, candidate_data in enumerate(position_data["candidates"]):
                Candidate.objects.create(
                    position=position,
                    name=candidate_data["name"],
                    class_name=candidate_data.get("class_name", ""),
                    motto=candidate_data.get("motto", ""),
                    photo=candidate_data.get("photo", ""),
                    symbol=candidate_data.get("symbol", ""),
                    order=c_index,
                    is_nota=candidate_data.get("is_nota", False),
                )

        self.stdout.write(self.style.SUCCESS(f"Seeded election: {election.title} for {election.school_name}"))
