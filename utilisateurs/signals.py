from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import JournalAudit


@receiver(user_logged_in)
def journaliser_connexion(sender, request, user, **kwargs):
    JournalAudit.enregistrer(user, "CONNEXION", f"Utilisateur {user.username}")


@receiver(user_logged_out)
def journaliser_deconnexion(sender, request, user, **kwargs):
    if user is not None:
        JournalAudit.enregistrer(user, "DECONNEXION", f"Utilisateur {user.username}")


@receiver(user_login_failed)
def journaliser_echec(sender, credentials, request=None, **kwargs):
    nom = credentials.get("username", "inconnu")
    JournalAudit.enregistrer(None, "ECHEC_CONNEXION", f"Identifiant saisi : {nom}")