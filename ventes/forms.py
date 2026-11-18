from django import forms

from clients.models import Client
from pharmacie.formulaires import BootstrapMixin

from .models import ModePaiement


class ValidationVenteForm(BootstrapMixin, forms.Form):
    client = forms.ModelChoiceField(
        queryset=Client.objects.none(), required=False,
        empty_label="Client comptoir (non identifié)", label="Client",
    )
    mode = forms.ChoiceField(choices=ModePaiement.choices, initial=ModePaiement.ESPECES, label="Mode de paiement")
    montant_recu = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Montant reçu (espèces)",
    )
    reference = forms.CharField(
        required=False, max_length=100, label="Référence de transaction",
        help_text="Mobile money / carte : le paiement restera « en attente » jusqu'à sa vérification.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(actif=True).order_by("nom")


class RetourForm(BootstrapMixin, forms.Form):
    ligne = forms.ChoiceField(label="Médicament et lot concernés")
    quantite = forms.IntegerField(min_value=1, label="Quantité retournée")
    motif = forms.CharField(max_length=255, label="Motif du retour")
    remis_en_stock = forms.BooleanField(
        required=False, label="Remettre le produit en stock",
        help_text="Cochez seulement si le produit est intact, scellé et éligible à la remise en stock.",
    )
    mode_remboursement = forms.ChoiceField(
        choices=ModePaiement.choices, initial=ModePaiement.ESPECES, label="Mode de remboursement",
    )

    def __init__(self, *args, vente=None, **kwargs):
        super().__init__(*args, **kwargs)
        choix = []
        for ligne in vente.lignes.select_related("medicament", "lot"):
            if ligne.quantite_retournable > 0:
                choix.append((
                    str(ligne.pk),
                    f"{ligne.medicament} — lot {ligne.lot.numero_lot} — "
                    f"{ligne.quantite_retournable} retournable(s) sur {ligne.quantite}",
                ))
        self.fields["ligne"].choices = choix


class AnnulationForm(BootstrapMixin, forms.Form):
    motif = forms.CharField(max_length=255, label="Motif de l'annulation")
