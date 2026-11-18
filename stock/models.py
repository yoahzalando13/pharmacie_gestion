from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def aujourd_hui():
    return timezone.localdate()


class LotQuerySet(models.QuerySet):
    """Filtres réutilisables sur les lots."""

    def vendables(self):
        """Lots qui peuvent être vendus : en stock, non bloqués, non périmés, médicament actif."""
        return self.filter(
            quantite__gt=0,
            bloque=False,
            date_peremption__gte=aujourd_hui(),
            medicament__statut="ACTIF",
        )

    def perimes(self):
        return self.filter(date_peremption__lt=aujourd_hui())

    def proches_peremption(self):
        limite = aujourd_hui() + timedelta(days=settings.PEREMPTION_ALERTE_JOURS)
        return self.filter(date_peremption__gte=aujourd_hui(), date_peremption__lte=limite)


class LotStock(models.Model):
    medicament = models.ForeignKey(
        "medicaments.Medicament",
        on_delete=models.PROTECT,
        related_name="lots",
        verbose_name="Médicament",
    )
    numero_lot = models.CharField("Numéro de lot", max_length=50)
    date_peremption = models.DateField("Date de péremption")
    quantite_recue = models.PositiveIntegerField("Quantité reçue", default=0)
    quantite = models.PositiveIntegerField("Quantité disponible", default=0)
    bloque = models.BooleanField("Bloqué", default=False)
    motif_blocage = models.CharField("Motif du blocage", max_length=255, blank=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)

    objects = LotQuerySet.as_manager()

    class Meta:
        ordering = ["date_peremption", "pk"]   # ordre FEFO : le premier qui périme sort en premier
        verbose_name = "Lot"
        verbose_name_plural = "Lots"
        constraints = [
            models.UniqueConstraint(fields=["medicament", "numero_lot"], name="lot_unique_par_medicament"),
        ]

    def __str__(self):
        return f"{self.medicament} — lot {self.numero_lot}"

    @property
    def est_perime(self):
        return self.date_peremption < aujourd_hui()

    @property
    def jours_restants(self):
        return (self.date_peremption - aujourd_hui()).days

    @property
    def est_proche_peremption(self):
        return not self.est_perime and self.jours_restants <= settings.PEREMPTION_ALERTE_JOURS

    @property
    def est_vendable(self):
        return (
            self.quantite > 0
            and not self.bloque
            and not self.est_perime
            and self.medicament.statut == "ACTIF"
        )


class MouvementStock(models.Model):
    """Historique de TOUTES les entrées et sorties. Une ligne ne se modifie jamais."""

    class Type(models.TextChoices):
        ENTREE_ACHAT = "ENTREE_ACHAT", "Entrée — réception d'achat"
        RETOUR_CLIENT = "RETOUR_CLIENT", "Entrée — retour client"
        CORRECTION_PLUS = "CORRECTION_PLUS", "Correction d'inventaire (+)"
        SORTIE_VENTE = "SORTIE_VENTE", "Sortie — vente"
        CORRECTION_MOINS = "CORRECTION_MOINS", "Correction d'inventaire (−)"
        SORTIE_PERTE = "SORTIE_PERTE", "Sortie — périmé, perte ou casse"

    TYPES_ENTREE = {Type.ENTREE_ACHAT, Type.RETOUR_CLIENT, Type.CORRECTION_PLUS}

    lot = models.ForeignKey(LotStock, on_delete=models.PROTECT, related_name="mouvements", verbose_name="Lot")
    type = models.CharField("Type", max_length=20, choices=Type.choices)
    quantite = models.PositiveIntegerField("Quantité")
    stock_avant = models.PositiveIntegerField("Stock avant")
    stock_apres = models.PositiveIntegerField("Stock après")
    reference = models.CharField("Référence", max_length=50, blank=True)   # ex : RE-2026-00003
    motif = models.CharField("Motif", max_length=255, blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mouvements_stock",
        verbose_name="Utilisateur",
    )
    date = models.DateTimeField("Date", auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"

    def __str__(self):
        return f"{self.get_type_display()} : {self.quantite} × {self.lot}"

    @property
    def est_entree(self):
        return self.type in self.TYPES_ENTREE