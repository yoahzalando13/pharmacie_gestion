from django.conf import settings
from django.db import models

from pharmacie.validateurs import valider_telephone


class Fournisseur(models.Model):
    nom = models.CharField("Nom ou raison sociale", max_length=150, unique=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    telephone = models.CharField("Téléphone", max_length=20, validators=[valider_telephone])
    email = models.EmailField("Adresse e-mail", blank=True)
    numero_fiscal = models.CharField("NIF / STAT", max_length=50, blank=True)
    contact_principal = models.CharField("Contact principal", max_length=150, blank=True)
    actif = models.BooleanField("Actif", default=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fournisseurs_crees",
        verbose_name="Créé par",
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.nom