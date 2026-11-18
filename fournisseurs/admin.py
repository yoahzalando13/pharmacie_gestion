from django.contrib import admin

from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "contact_principal", "email", "actif")
    list_filter = ("actif",)
    search_fields = ("nom", "telephone", "contact_principal")
    readonly_fields = ("date_creation", "cree_par")