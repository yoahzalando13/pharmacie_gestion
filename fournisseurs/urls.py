from django.urls import path

from . import views

urlpatterns = [
    path("", views.fournisseur_liste, name="fournisseur_liste"),
    path("ajouter/", views.fournisseur_creer, name="fournisseur_creer"),
    path("<int:pk>/", views.fournisseur_detail, name="fournisseur_detail"),
    path("<int:pk>/modifier/", views.fournisseur_modifier, name="fournisseur_modifier"),
    path("<int:pk>/statut/", views.fournisseur_basculer_actif, name="fournisseur_basculer_actif"),
    path("<int:pk>/supprimer/", views.fournisseur_supprimer, name="fournisseur_supprimer"),
]