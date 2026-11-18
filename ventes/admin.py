from django.contrib import admin

from stock.admin import LectureSeuleAdmin

from .models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PaiementInline(LigneVenteInline):
    model = Paiement
    fk_name = "vente"


@admin.register(Vente)
class VenteAdmin(LectureSeuleAdmin):
    """Les ventes ne se modifient jamais depuis l'admin : retours et annulations passent par l'application (RG10)."""
    list_display = ("numero", "date", "client", "total", "statut", "vendeur")
    list_filter = ("statut",)
    search_fields = ("numero", "client__nom")
    exclude = ("jeton",)
    inlines = [LigneVenteInline, PaiementInline]


@admin.register(RetourVente)
class RetourVenteAdmin(LectureSeuleAdmin):
    list_display = ("numero", "date", "vente", "ligne", "quantite", "montant_rembourse", "remis_en_stock", "utilisateur")
    search_fields = ("numero", "vente__numero")
