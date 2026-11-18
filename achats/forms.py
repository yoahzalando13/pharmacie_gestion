from django import forms
from django.utils import timezone

from fournisseurs.models import Fournisseur
from medicaments.models import Medicament
from pharmacie.formulaires import BootstrapMixin

from .models import CommandeAchat, LigneAchat


class CommandeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CommandeAchat
        fields = ["fournisseur", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fournisseur"].queryset = Fournisseur.objects.filter(actif=True)


class LigneAchatForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = LigneAchat
        fields = ["medicament", "quantite_commandee", "prix_achat"]

    def __init__(self, *args, commande=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.commande = commande
        self.fields["medicament"].queryset = Medicament.objects.filter(statut="ACTIF").order_by("nom")
        self.fields["prix_achat"].required = False
        self.fields["prix_achat"].widget.attrs["placeholder"] = "Prix de la fiche"

    def clean(self):
        donnees = super().clean()
        medicament = donnees.get("medicament")
        if medicament:
            if not donnees.get("prix_achat"):
                donnees["prix_achat"] = medicament.prix_achat
            if self.commande and self.commande.lignes.filter(medicament=medicament).exists():
                self.add_error("medicament", "Ce médicament est déjà dans la commande. Supprimez la ligne pour la modifier.")
        return donnees


class LigneReceptionForm(BootstrapMixin, forms.Form):
    ligne_id = forms.IntegerField(widget=forms.HiddenInput)
    quantite = forms.IntegerField(min_value=0, label="Quantité reçue")
    numero_lot = forms.CharField(max_length=50, required=False, label="N° de lot")
    date_peremption = forms.DateField(
        required=False,
        label="Date de péremption",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def clean(self):
        donnees = super().clean()
        if donnees.get("quantite"):
            if not donnees.get("numero_lot", "").strip():
                self.add_error("numero_lot", "Obligatoire si la quantité est supérieure à 0.")
            date_peremption = donnees.get("date_peremption")
            if not date_peremption:
                self.add_error("date_peremption", "Obligatoire si la quantité est supérieure à 0.")
            elif date_peremption <= timezone.localdate():
                self.add_error("date_peremption", "Ce lot est déjà périmé : réception refusée.")
        return donnees


LigneReceptionFormSet = forms.formset_factory(LigneReceptionForm, extra=0)