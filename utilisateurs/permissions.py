from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

# Noms des rôles (= noms des groupes Django)
ADMIN = "Administrateur"
PHARMACIEN = "Pharmacien responsable"
STOCK = "Gestionnaire de stock"
CAISSIER = "Caissier"
GESTION = "Responsable de gestion"

TOUS_LES_ROLES = [ADMIN, PHARMACIEN, STOCK, CAISSIER, GESTION]


def a_un_role(user, *roles):
    """Vrai si l'utilisateur possède au moins un des rôles donnés."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


def role_requis(*roles):
    """
    Décorateur à placer sur une vue :
        @role_requis(CAISSIER, PHARMACIEN)
    L'administrateur a toujours accès.
    """
    def decorateur(vue):
        @wraps(vue)
        @login_required
        def vue_protegee(request, *args, **kwargs):
            if a_un_role(request.user, ADMIN, *roles):
                return vue(request, *args, **kwargs)
            raise PermissionDenied  # page 403 "Accès interdit"
        return vue_protegee
    return decorateur