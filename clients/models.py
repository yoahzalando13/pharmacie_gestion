from django.conf import settings
from django.db import models

from pharmacie.validateurs import valider_telephone


class Client(models.Model):
    """
    Données limitées au strict nécessaire (cahier des charges, module E).
    Une vente comptoir pourra se faire sans client (client anonyme).
    """
    nom = models.CharField("Nom", max_length=150)
    telephone = models.CharField("Téléphone", max_length=20, blank=True, validators=[valider_telephone])
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    email = models.EmailField("Adresse e-mail", blank=True)
    actif = models.BooleanField("Compte actif", default=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="clients_crees",
        verbose_name="Créé par",
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return f"{self.nom} ({self.telephone})" if self.telephone else self.nom