from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DecimalField, F, Sum

MONTANT = DecimalField(max_digits=14, decimal_places=2)


class ModePaiement(models.TextChoices):
    ESPECES = "ESPECES", "Espèces"
    MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
    CARTE = "CARTE", "Carte bancaire"
    CHEQUE = "CHEQUE", "Chèque"


# Modes dont l'encaissement doit être vérifié avant d'être considéré comme confirmé (§4.8)
MODES_A_VERIFIER = {ModePaiement.MOBILE_MONEY, ModePaiement.CARTE, ModePaiement.CHEQUE}


class Vente(models.Model):
    class Statut(models.TextChoices):
        VALIDEE = "VALIDEE", "Validée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("Numéro", max_length=20, unique=True, null=True, blank=True, editable=False)
    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, null=True, blank=True,
        related_name="ventes", verbose_name="Client",
    )
    statut = models.CharField("Statut", max_length=10, choices=Statut.choices, default=Statut.VALIDEE)
    total = models.DecimalField("Total", max_digits=14, decimal_places=2, default=Decimal("0"))
    date = models.DateTimeField("Date", auto_now_add=True)
    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventes", verbose_name="Vendeur",
    )
    # Jeton unique du formulaire de caisse : empêche la double validation (§4.8, §8.1)
    jeton = models.CharField(max_length=32, unique=True, editable=False)

    date_annulation = models.DateTimeField("Date d'annulation", null=True, blank=True)
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="ventes_annulees",
    )
    motif_annulation = models.CharField("Motif d'annulation", max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"

    def __str__(self):
        return self.numero or f"Vente #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f"VE-{self.date:%Y}-{self.pk:05d}"
            super().save(update_fields=["numero"])

    @property
    def montant_paye(self):
        return self.paiements.filter(statut=Paiement.Statut.CONFIRME).aggregate(
            t=Sum("montant"))["t"] or Decimal("0")

    @property
    def montant_rembourse(self):
        return self.retours.aggregate(t=Sum("montant_rembourse"))["t"] or Decimal("0")

    @property
    def paiement_en_attente(self):
        return self.paiements.filter(statut=Paiement.Statut.EN_ATTENTE).exists()

    @property
    def couleur_statut(self):
        return "success" if self.statut == self.Statut.VALIDEE else "danger"


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="lignes")
    medicament = models.ForeignKey(
        "medicaments.Medicament", on_delete=models.PROTECT, related_name="lignes_vente",
    )
    lot = models.ForeignKey("stock.LotStock", on_delete=models.PROTECT, related_name="lignes_vente")
    quantite = models.PositiveIntegerField("Quantité", validators=[MinValueValidator(1)])
    # Prix figés au moment de la vente (RG12) : une hausse de prix ne change pas les anciennes ventes
    prix_unitaire = models.DecimalField("Prix unitaire appliqué", max_digits=12, decimal_places=2)
    cout_unitaire = models.DecimalField("Coût d'achat unitaire", max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"

    def __str__(self):
        return f"{self.quantite} × {self.medicament}"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire

    @property
    def quantite_retournee(self):
        return self.retours.aggregate(t=Sum("quantite"))["t"] or 0

    @property
    def quantite_retournable(self):
        return self.quantite - self.quantite_retournee


class Paiement(models.Model):
    class Statut(models.TextChoices):
        CONFIRME = "CONFIRME", "Confirmé"
        EN_ATTENTE = "EN_ATTENTE", "En attente de vérification"
        REJETE = "REJETE", "Rejeté"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="paiements")
    mode = models.CharField("Mode de paiement", max_length=20, choices=ModePaiement.choices)
    montant = models.DecimalField("Montant", max_digits=14, decimal_places=2)
    montant_recu = models.DecimalField("Montant reçu", max_digits=14, decimal_places=2, null=True, blank=True)
    reference = models.CharField("Référence de transaction", max_length=100, blank=True)
    statut = models.CharField("Statut", max_length=12, choices=Statut.choices, default=Statut.CONFIRME)
    date = models.DateTimeField("Date", auto_now_add=True)
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="paiements_enregistres",
    )
    date_verification = models.DateTimeField("Date de vérification", null=True, blank=True)
    verifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="paiements_verifies",
    )

    class Meta:
        ordering = ["-date"]
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def __str__(self):
        return f"{self.get_mode_display()} — {self.montant} Ar ({self.get_statut_display()})"

    @property
    def monnaie_rendue(self):
        if self.montant_recu is None:
            return None
        return max(self.montant_recu - self.montant, Decimal("0"))


class RetourVente(models.Model):
    """Retour d'un produit : opération compensatoire, la vente d'origine reste intacte (§4.9)."""

    numero = models.CharField("Numéro", max_length=20, unique=True, null=True, blank=True, editable=False)
    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="retours")
    ligne = models.ForeignKey(LigneVente, on_delete=models.PROTECT, related_name="retours")
    quantite = models.PositiveIntegerField("Quantité retournée", validators=[MinValueValidator(1)])
    motif = models.CharField("Motif du retour", max_length=255)
    remis_en_stock = models.BooleanField(
        "Remettre en stock", default=False,
        help_text="Uniquement si le produit est intact, non périmé et éligible à la remise en stock.",
    )
    montant_rembourse = models.DecimalField("Montant remboursé", max_digits=14, decimal_places=2)
    mode_remboursement = models.CharField(
        "Mode de remboursement", max_length=20, choices=ModePaiement.choices, default=ModePaiement.ESPECES,
    )
    date = models.DateTimeField("Date", auto_now_add=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="retours_vente",
    )

    class Meta:
        ordering = ["-date"]
        verbose_name = "Retour de vente"
        verbose_name_plural = "Retours de vente"

    def __str__(self):
        return self.numero or f"Retour #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f"RV-{self.date:%Y}-{self.pk:05d}"
            super().save(update_fields=["numero"])


def total_lignes(queryset):
    """Somme quantité × prix d'un queryset de LigneVente."""
    return queryset.aggregate(t=Sum(F("quantite") * F("prix_unitaire"), output_field=MONTANT))["t"] or Decimal("0")
