from django import forms

from pharmacie.formulaires import BootstrapMixin

from .models import Fournisseur


class FournisseurForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ["nom", "telephone", "email", "contact_principal", "numero_fiscal", "adresse"]
        widgets = {"adresse": forms.Textarea(attrs={"rows": 2})}