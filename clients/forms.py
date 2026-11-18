from django import forms

from pharmacie.formulaires import BootstrapMixin

from .models import Client


class ClientForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ["nom", "telephone", "email", "adresse"]
        widgets = {"adresse": forms.Textarea(attrs={"rows": 2})}