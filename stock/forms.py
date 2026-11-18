from django import forms

from pharmacie.formulaires import BootstrapMixin

from .models import MouvementStock


class CorrectionForm(BootstrapMixin, forms.Form):
    type = forms.ChoiceField(
        label="Type de correction",
        choices=[
            (MouvementStock.Type.CORRECTION_PLUS, MouvementStock.Type.CORRECTION_PLUS.label),
            (MouvementStock.Type.CORRECTION_MOINS, MouvementStock.Type.CORRECTION_MOINS.label),
            (MouvementStock.Type.SORTIE_PERTE, MouvementStock.Type.SORTIE_PERTE.label),
        ],
    )
    quantite = forms.IntegerField(label="Quantité", min_value=1)
    motif = forms.CharField(
        label="Motif", max_length=255,
        help_text="Obligatoire : erreur de comptage, casse, destruction d'un lot périmé…",
    )


class BlocageForm(BootstrapMixin, forms.Form):
    motif = forms.CharField(label="Motif du blocage", max_length=255, required=False)
