from django.contrib import admin

from .models import LotStock, MouvementStock


class LectureSeuleAdmin(admin.ModelAdmin):
    """Consultation uniquement : les modifications passent par l'application."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LotStock)
class LotStockAdmin(LectureSeuleAdmin):
    list_display = ("medicament", "numero_lot", "date_peremption", "quantite_recue", "quantite", "bloque")
    list_filter = ("bloque",)
    search_fields = ("numero_lot", "medicament__nom")


@admin.register(MouvementStock)
class MouvementStockAdmin(LectureSeuleAdmin):
    list_display = ("date", "type", "lot", "quantite", "stock_avant", "stock_apres", "utilisateur", "reference")
    list_filter = ("type",)
    search_fields = ("lot__numero_lot", "lot__medicament__nom", "reference")