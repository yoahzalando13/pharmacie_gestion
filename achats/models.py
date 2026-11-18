from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DecimalField, F, Sum

MONTANT = DecimalField(max_digits=14, decimal_places=2)


class CommandeAchat(models.Model):

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        COMMANDEE = "COMMANDEE", "Commandée"
        PARTIELLE = "PARTIELLE", "Partiellement réceptionnée"
        RECUE = "RECUE", "Entièrement réceptionnée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("Numéro", max_length=20, unique=True, null=True, blank=True, editable=False)
    fournisseur = models.ForeignKey(
        "fournisseurs.Fournisseur", on_delete=models.PROTECT,
        related_name="commandes", verbose_name="Fournisseur",
    )
    statut = models.CharField("Statut", max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField("Note", blank=True)

    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commandes_creees",
    )
    date_validation = models.DateTimeField("Date de validation", null=True, blank=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="commandes_validees",
    )
    date_annulation = models.DateTimeField("Date d'annulation", null=True, blank=True)
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="commandes_annulees",
    )

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Commande d'achat"
        verbose_name_plural = "Commandes d'achat"

    def __str__(self):
        return self.numero or f"Commande #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f"CA-{self.date_creation:%Y}-{self.pk:05d}"
            super().save(update_fields=["numero"])

    @property
    def total(self):
        resultat = self.lignes.aggregate(
            t=Sum(F("quantite_commandee") * F("prix_achat"), output_field=MONTANT)
        )["t"]
        return resultat or Decimal("0")

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def peut_etre_receptionnee(self):
        return self.statut in (self.Statut.COMMANDEE, self.Statut.PARTIELLE)

    @property
    def peut_etre_annulee(self):
        # Une commande déjà (partiellement) reçue ne s'annule pas : le stock a bougé
        return self.statut in (self.Statut.BROUILLON, self.Statut.COMMANDEE)

    @property
    def couleur_statut(self):
        return {
            self.Statut.BROUILLON: "secondary",
            self.Statut.COMMANDEE: "primary",
            self.Statut.PARTIELLE: "warning",
            self.Statut.RECUE: "success",
            self.Statut.ANNULEE: "danger",
        }.get(self.statut, "secondary")

    def mettre_a_jour_statut(self):
        """Après une réception : PARTIELLE ou RECUE selon ce qui reste à recevoir."""
        tout_recu = all(ligne.reste_a_recevoir == 0 for ligne in self.lignes.all())
        self.statut = self.Statut.RECUE if tout_recu else self.Statut.PARTIELLE
        self.save(update_fields=["statut"])


class LigneAchat(models.Model):
    commande = models.ForeignKey(CommandeAchat, on_delete=models.CASCADE, related_name="lignes")
    medicament = models.ForeignKey(
        "medicaments.Medicament", on_delete=models.PROTECT,
        related_name="lignes_achat", verbose_name="Médicament",
    )
    quantite_commandee = models.PositiveIntegerField("Quantité", validators=[MinValueValidator(1)])
    prix_achat = models.DecimalField(
        "Prix d'achat unitaire", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    quantite_recue = models.PositiveIntegerField("Quantité reçue", default=0)

    class Meta:
        ordering = ["pk"]
        verbose_name = "Ligne d'achat"
        verbose_name_plural = "Lignes d'achat"
        constraints = [
            models.UniqueConstraint(fields=["commande", "medicament"], name="ligne_achat_unique"),
        ]

    def __str__(self):
        return f"{self.quantite_commandee} × {self.medicament}"

    @property
    def montant(self):
        return self.quantite_commandee * self.prix_achat

    @property
    def reste_a_recevoir(self):
        return max(self.quantite_commandee - self.quantite_recue, 0)


class ReceptionAchat(models.Model):
    numero = models.CharField("Numéro", max_length=20, unique=True, null=True, blank=True, editable=False)
    commande = models.ForeignKey(CommandeAchat, on_delete=models.PROTECT, related_name="receptions")
    date_reception = models.DateTimeField("Date de réception", auto_now_add=True)
    recu_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="receptions")
    note = models.TextField("Note", blank=True)
    # Jeton unique du formulaire : empêche d'enregistrer deux fois la même réception (RG05)
    jeton = models.CharField(max_length=32, unique=True, editable=False)

    class Meta:
        ordering = ["-date_reception"]
        verbose_name = "Réception"
        verbose_name_plural = "Réceptions"

    def __str__(self):
        return self.numero or f"Réception #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f"RE-{self.date_reception:%Y}-{self.pk:05d}"
            super().save(update_fields=["numero"])

    @property
    def total(self):
        resultat = self.lignes.aggregate(
            t=Sum(F("quantite") * F("prix_achat"), output_field=MONTANT)
        )["t"]
        return resultat or Decimal("0")


class LigneReception(models.Model):
    reception = models.ForeignKey(ReceptionAchat, on_delete=models.CASCADE, related_name="lignes")
    ligne_achat = models.ForeignKey(LigneAchat, on_delete=models.PROTECT, related_name="lignes_reception")
    lot = models.ForeignKey("stock.LotStock", on_delete=models.PROTECT, related_name="lignes_reception")
    quantite = models.PositiveIntegerField("Quantité reçue", validators=[MinValueValidator(1)])
    prix_achat = models.DecimalField("Prix d'achat unitaire", max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        verbose_name = "Ligne de réception"
        verbose_name_plural = "Lignes de réception"

    @property
    def montant(self):
        return self.quantite * self.prix_achat