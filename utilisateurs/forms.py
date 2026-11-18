from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import Group

from pharmacie.formulaires import BootstrapMixin

from .models import Utilisateur
from .permissions import TOUS_LES_ROLES


def champ_roles():
    """Champ « Rôles » : cases à cocher avec les 5 groupes de PharmaGest."""
    return forms.ModelMultipleChoiceField(
        queryset=Group.objects.filter(name__in=TOUS_LES_ROLES).order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Rôles",
        help_text="Un utilisateur peut cumuler plusieurs rôles.",
    )


class UtilisateurCreationForm(BootstrapMixin, UserCreationForm):
    roles = champ_roles()

    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = ("username", "first_name", "last_name", "email", "telephone")

    def save(self, commit=True):
        utilisateur = super().save(commit=commit)
        if commit:
            utilisateur.groups.set(self.cleaned_data["roles"])
        return utilisateur


class UtilisateurModificationForm(BootstrapMixin, forms.ModelForm):
    roles = champ_roles()

    class Meta:
        model = Utilisateur
        fields = ["username", "first_name", "last_name", "email", "telephone", "is_active"]
        labels = {"is_active": "Compte actif"}

    def __init__(self, *args, utilisateur_connecte=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].initial = self.instance.groups.all()

        # Sécurité : on ne peut pas se retirer ses propres rôles ni se désactiver soi-même
        if utilisateur_connecte is not None and self.instance.pk == utilisateur_connecte.pk:
            self.fields["roles"].disabled = True
            self.fields["is_active"].disabled = True
            self.fields["roles"].help_text = "Vous ne pouvez pas modifier vos propres rôles."

    def save(self, commit=True):
        utilisateur = super().save(commit=commit)
        if commit:
            utilisateur.groups.set(self.cleaned_data["roles"])
        return utilisateur


class ReinitialisationMotDePasseForm(BootstrapMixin, SetPasswordForm):
    """L'administrateur définit un nouveau mot de passe pour un utilisateur."""


class ChangementMotDePasseForm(BootstrapMixin, PasswordChangeForm):
    """L'utilisateur change son propre mot de passe (ancien mot de passe obligatoire)."""