import shutil
import sqlite3
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Sauvegarde la base SQLite et les fichiers média (photos) dans le dossier « sauvegardes »."

    def handle(self, *args, **options):
        base = settings.DATABASES["default"]
        if base["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Cette commande ne gère que SQLite. Pour PostgreSQL, utilisez pg_dump.")

        dossier = settings.SAUVEGARDES_DIR
        dossier.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")

        # API de sauvegarde SQLite : copie cohérente même si l'application est en cours d'utilisation
        cible = dossier / f"pharmagest_{horodatage}.sqlite3"
        source = sqlite3.connect(base["NAME"])
        destination = sqlite3.connect(cible)
        with destination:
            source.backup(destination)
        source.close()
        destination.close()

        # Vérification : la copie doit être lisible et intègre
        verif = sqlite3.connect(cible)
        etat = verif.execute("PRAGMA integrity_check").fetchone()[0]
        verif.close()
        if etat != "ok":
            raise CommandError(f"La sauvegarde {cible.name} est corrompue : {etat}")
        self.stdout.write(self.style.SUCCESS(f"Base sauvegardée et vérifiée : {cible}"))

        media = settings.MEDIA_ROOT
        if media.exists():
            archive = shutil.make_archive(str(dossier / f"media_{horodatage}"), "zip", media)
            self.stdout.write(self.style.SUCCESS(f"Photos sauvegardées : {archive}"))
