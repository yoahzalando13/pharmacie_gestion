from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """
    Utilisateur de PharmaGest.
    Les rôles (Caissier, Pharmacien...) sont gérés avec les Groupes Django,
    ce qui permet à un utilisateur de cumuler plusieurs rôles si l'admin le décide.
    """
    telephone = models.CharField("Téléphone", max_length=20, blank=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.get_full_name() or self.username


class JournalAudit(models.Model):
    """Trace des opérations sensibles (RG09) : qui, quoi, quand."""
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="actions_journal",
    )
    action = models.CharField(max_length=50)       # ex : "CREATION", "VENTE", "ANNULATION"
    objet = models.CharField(max_length=150)       # ex : "Vente #12"
    details = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Entrée du journal"
        verbose_name_plural = "Journal d'audit"

    def __str__(self):
        return f"{self.date:%d/%m/%Y %H:%M} - {self.utilisateur} - {self.action} - {self.objet}"

    @classmethod
    def enregistrer(cls, utilisateur, action, objet, details=""):
        """Raccourci pour écrire dans le journal depuis n'importe quelle vue."""
        if utilisateur is not None and not utilisateur.is_authenticated:
            utilisateur = None
        return cls.objects.create(
            utilisateur=utilisateur, action=action, objet=str(objet), details=details
        )