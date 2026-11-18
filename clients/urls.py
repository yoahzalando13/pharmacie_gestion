from django.urls import path

from . import views

urlpatterns = [
    path("", views.client_liste, name="client_liste"),
    path("ajouter/", views.client_creer, name="client_creer"),
    path("<int:pk>/", views.client_detail, name="client_detail"),
    path("<int:pk>/modifier/", views.client_modifier, name="client_modifier"),
    path("<int:pk>/statut/", views.client_basculer_actif, name="client_basculer_actif"),
    path("<int:pk>/supprimer/", views.client_supprimer, name="client_supprimer"),
]