from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from pharmacie.formulaires import BootstrapMixin

from .models import Categorie, Medicament

TAILLE_MAX_PHOTO = 2 * 1024 * 1024          # 2 Mo
FORMATS_AUTORISES = ("JPEG", "PNG", "WEBP")


class CategorieForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class MedicamentForm(BootstrapMixin, forms.ModelForm):
    categorie = forms.ModelChoiceField(
        queryset=Categorie.objects.none(),       # rempli dans __init__
        required=False,
        empty_label="— Choisir une catégorie —",
        label="Catégorie",
    )
    nouvelle_categorie = forms.CharField(
        max_length=100,
        required=False,
        label="Ou créer une nouvelle catégorie",
        help_text="Laissez vide si vous avez choisi une catégorie dans la liste.",
    )

    class Meta:
        model = Medicament
        fields = [
            "nom", "dci", "categorie", "forme", "dosage", "laboratoire",
            "code_barres", "prix_achat", "prix_vente", "seuil_alerte", "photo",
        ]
        widgets = {
            "photo": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categorie"].queryset = Categorie.objects.order_by("nom")
        ordre = list(self.fields)
        ordre.remove("nouvelle_categorie")
        ordre.insert(ordre.index("categorie") + 1, "nouvelle_categorie")
        self.order_fields(ordre)

    def clean_code_barres(self):
        code = (self.cleaned_data.get("code_barres") or "").strip()
        return code or None   # vide → None, pour ne pas bloquer l'unicité (RG02)

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if isinstance(photo, UploadedFile):
            if photo.size > TAILLE_MAX_PHOTO:
                raise ValidationError("La photo ne doit pas dépasser 2 Mo.")
            image = getattr(photo, "image", None)
            if image is None or image.format not in FORMATS_AUTORISES:
                raise ValidationError("Formats acceptés : JPEG, PNG ou WEBP.")
        return photo

    def clean(self):
        donnees = super().clean()

        categorie = donnees.get("categorie")
        nouvelle = (donnees.get("nouvelle_categorie") or "").strip()

        if categorie and nouvelle:
            self.add_error("nouvelle_categorie",
                           "Choisissez une catégorie dans la liste OU saisissez-en une nouvelle, pas les deux.")
        elif not categorie and not nouvelle:
            self.add_error("categorie", "Veuillez choisir ou créer une catégorie.")
        elif nouvelle:
            existante = Categorie.objects.filter(nom__iexact=nouvelle).first()
            if existante:
                donnees["categorie"] = existante
                donnees["nouvelle_categorie"] = ""
            else:
                donnees["nouvelle_categorie"] = nouvelle

        prix_achat = donnees.get("prix_achat")
        prix_vente = donnees.get("prix_vente")
        if prix_achat and prix_vente and prix_vente < prix_achat:
            self.add_error("prix_vente", "Le prix de vente ne peut pas être inférieur au prix d'achat.")
        return donnees

    def save(self, commit=True):
        nouvelle = self.cleaned_data.get("nouvelle_categorie")
        if nouvelle:
            self.instance.categorie = Categorie.objects.create(nom=nouvelle)
        else:
            self.instance.categorie = self.cleaned_data["categorie"]
        return super().save(commit=commit)