from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from utilisateurs.permissions import TOUS_LES_ROLES


class Command(BaseCommand):
    help = "Crée les groupes (rôles) de PharmaGest"

    def handle(self, *args, **options):
        for nom in TOUS_LES_ROLES:
            groupe, cree = Group.objects.get_or_create(name=nom)
            etat = "créé" if cree else "existe déjà"
            self.stdout.write(self.style.SUCCESS(f"Rôle « {nom} » : {etat}"))