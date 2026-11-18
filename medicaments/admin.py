from django.contrib import admin

from .models import Categorie, Medicament


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "description")
    search_fields = ("nom",)


@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = ("nom", "dosage", "forme", "categorie", "prix_vente", "statut")
    list_filter = ("categorie", "forme", "statut")
    search_fields = ("nom", "dci", "code_barres")
    readonly_fields = ("date_creation", "cree_par")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)