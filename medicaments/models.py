from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Categorie(models.Model):
    nom = models.CharField("Nom", max_length=100, unique=True)
    description = models.TextField("Description", blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.nom


class Medicament(models.Model):

    class Forme(models.TextChoices):
        COMPRIME = "COMPRIME", "Comprimé"
        GELULE = "GELULE", "Gélule"
        SIROP = "SIROP", "Sirop"
        INJECTABLE = "INJECTABLE", "Injectable"
        POMMADE = "POMMADE", "Pommade / Crème"
        SUPPOSITOIRE = "SUPPOSITOIRE", "Suppositoire"
        COLLYRE = "COLLYRE", "Collyre"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        ARCHIVE = "ARCHIVE", "Archivé"

    nom = models.CharField("Nom commercial", max_length=150)
    dci = models.CharField("Dénomination générique (DCI)", max_length=150, blank=True)
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,   # empêche de supprimer une catégorie utilisée
        related_name="medicaments",
        verbose_name="Catégorie",
    )
    forme = models.CharField("Forme", max_length=20, choices=Forme.choices, default=Forme.COMPRIME)
    dosage = models.CharField("Dosage", max_length=50, blank=True, help_text="Ex : 500 mg")
    laboratoire = models.CharField("Laboratoire", max_length=150, blank=True)
    code_barres = models.CharField(
        "Code-barres", max_length=50, unique=True, null=True, blank=True
    )
    photo = models.ImageField("Photo", upload_to="medicaments/", null=True, blank=True)
    prix_achat = models.DecimalField(
        "Prix d'achat", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    prix_vente = models.DecimalField(
        "Prix de vente", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    seuil_alerte = models.PositiveIntegerField("Seuil d'alerte", default=10)
    statut = models.CharField("Statut", max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="medicaments_crees",
        verbose_name="Créé par",
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "Médicament"
        verbose_name_plural = "Médicaments"

    def __str__(self):
        return f"{self.nom} {self.dosage}".strip()

    def save(self, *args, **kwargs):
        # Un code-barres vide devient NULL, sinon deux médicaments sans code
        # seraient considérés comme des doublons (RG02).
        if not self.code_barres:
            self.code_barres = None
        super().save(*args, **kwargs)

    # ---------------------------------------------------------------- Stock
    # Le stock n'est jamais saisi à la main : il est calculé à partir des lots (§4.7).

    @property
    def stock_total(self):
        return self.lots.aggregate(t=models.Sum("quantite"))["t"] or 0

    @property
    def stock_vendable(self):
        return self.lots.vendables().aggregate(t=models.Sum("quantite"))["t"] or 0

    @property
    def est_en_rupture(self):
        return self.stock_vendable == 0

    @property
    def est_sous_seuil(self):
        return self.stock_vendable <= self.seuil_alerte
