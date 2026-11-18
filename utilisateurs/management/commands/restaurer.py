import shutil
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restaure une sauvegarde : python manage.py restaurer sauvegardes/pharmagest_AAAAMMJJ_HHMMSS.sqlite3 --oui"

    def add_arguments(self, parser):
        parser.add_argument("fichier", help="Fichier .sqlite3 créé par « python manage.py sauvegarder »")
        parser.add_argument("--oui", action="store_true", help="Confirme le remplacement de la base actuelle")

    def handle(self, *args, fichier, oui, **options):
        source = Path(fichier)
        if not source.exists():
            raise CommandError(f"Fichier introuvable : {source}")

        verif = sqlite3.connect(source)
        etat = verif.execute("PRAGMA integrity_check").fetchone()[0]
        verif.close()
        if etat != "ok":
            raise CommandError(f"Sauvegarde corrompue ({etat}) : restauration annulée.")

        if not oui:
            raise CommandError(
                "Attention : la base actuelle va être remplacée. Arrêtez le serveur, puis relancez avec --oui."
            )

        actuelle = Path(settings.DATABASES["default"]["NAME"])
        if actuelle.exists():
            filet = actuelle.with_name(actuelle.stem + "_avant_restauration.sqlite3")
            shutil.copy2(actuelle, filet)
            self.stdout.write(f"Base actuelle conservée dans {filet}")

        shutil.copy2(source, actuelle)
        self.stdout.write(self.style.SUCCESS(f"Base restaurée depuis {source}"))

        archive_media = source.with_name(source.name.replace("pharmagest_", "media_").replace(".sqlite3", ".zip"))
        if archive_media.exists():
            shutil.unpack_archive(archive_media, settings.MEDIA_ROOT)
            self.stdout.write(self.style.SUCCESS(f"Photos restaurées depuis {archive_media}"))
