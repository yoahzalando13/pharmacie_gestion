from django.urls import path

from . import views

urlpatterns = [
    path("", views.commande_liste, name="commande_liste"),
    path("nouvelle/", views.commande_creer, name="commande_creer"),
    path("<int:pk>/", views.commande_detail, name="commande_detail"),
    path("<int:pk>/valider/", views.commande_valider, name="commande_valider"),
    path("<int:pk>/annuler/", views.commande_annuler, name="commande_annuler"),
    path("<int:pk>/lignes/<int:ligne_pk>/supprimer/", views.ligne_supprimer, name="ligne_supprimer"),
    path("<int:pk>/receptionner/", views.reception_creer, name="reception_creer"),
    path("receptions/<int:pk>/", views.reception_detail, name="reception_detail"),
]