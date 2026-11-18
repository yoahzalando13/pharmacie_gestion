from django import template

from utilisateurs.permissions import ADMIN, a_un_role

register = template.Library()


@register.filter
def a_role(user, roles):
    """
    Utilisation dans un template :
        {% load roles %}
        {% if user|a_role:"Pharmacien responsable,Caissier" %} ... {% endif %}
    L'administrateur est toujours accepté.
    """
    liste = [r.strip() for r in roles.split(",") if r.strip()]
    return a_un_role(user, ADMIN, *liste)