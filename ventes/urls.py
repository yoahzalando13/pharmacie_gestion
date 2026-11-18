from django.urls import path

from . import views

urlpatterns = [
    path("", views.vente_liste, name="vente_liste"),
    path("caisse/", views.caisse, name="caisse"),
    path("<int:pk>/", views.vente_detail, name="vente_detail"),
    path("<int:pk>/retour/", views.retour_creer, name="retour_creer"),
    path("<int:pk>/annuler/", views.vente_annuler, name="vente_annuler"),
    path("paiements/<int:pk>/verifier/", views.paiement_verifier, name="paiement_verifier"),
]
