from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import JournalAudit, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Informations PharmaGest", {"fields": ("telephone",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Informations PharmaGest", {"fields": ("first_name", "last_name", "email", "telephone")}),
    )
    list_display = ("username", "first_name", "last_name", "is_active", "liste_roles")

    @admin.display(description="Rôles")
    def liste_roles(self, obj):
        return ", ".join(g.name for g in obj.groups.all()) or "—"


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("date", "utilisateur", "action", "objet")
    list_filter = ("action",)
    search_fields = ("objet", "details", "utilisateur__username")

    # Le journal est en lecture seule : personne ne peut le modifier
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False