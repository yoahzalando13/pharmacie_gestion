from django.contrib import admin

from stock.admin import LectureSeuleAdmin

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class LigneReceptionInline(LigneAchatInline):
    model = LigneReception


@admin.register(CommandeAchat)
class CommandeAchatAdmin(LectureSeuleAdmin):
    list_display = ("numero", "fournisseur", "statut", "date_creation", "cree_par")
    list_filter = ("statut",)
    search_fields = ("numero", "fournisseur__nom")
    inlines = [LigneAchatInline]


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(LectureSeuleAdmin):
    list_display = ("numero", "commande", "date_reception", "recu_par")
    search_fields = ("numero", "commande__numero")
    exclude = ("jeton",)
    inlines = [LigneReceptionInline]