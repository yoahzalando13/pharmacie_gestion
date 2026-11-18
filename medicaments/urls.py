from django.urls import path

from . import views

urlpatterns = [
    # Médicaments
    path("", views.medicament_liste, name="medicament_liste"),
    path("ajouter/", views.medicament_creer, name="medicament_creer"),
    path("<int:pk>/", views.medicament_detail, name="medicament_detail"),
    path("<int:pk>/modifier/", views.medicament_modifier, name="medicament_modifier"),
    path("<int:pk>/statut/", views.medicament_basculer_statut, name="medicament_basculer_statut"),
    path("<int:pk>/supprimer/", views.medicament_supprimer, name="medicament_supprimer"),

    # Catégories
    path("categories/", views.categorie_liste, name="categorie_liste"),
    path("categories/ajouter/", views.categorie_creer, name="categorie_creer"),
    path("categories/<int:pk>/modifier/", views.categorie_modifier, name="categorie_modifier"),
    path("categories/<int:pk>/supprimer/", views.categorie_supprimer, name="categorie_supprimer"),
]