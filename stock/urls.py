from django.urls import path

from . import views

urlpatterns = [
    path("", views.stock_liste, name="stock_liste"),
    path("alertes/", views.alertes, name="stock_alertes"),
    path("mouvements/", views.mouvement_liste, name="mouvement_liste"),
    path("inventaire/", views.inventaire, name="inventaire"),
    path("medicament/<int:pk>/", views.stock_medicament, name="stock_medicament"),
    path("lots/<int:lot_pk>/corriger/", views.correction_creer, name="correction_creer"),
    path("lots/<int:lot_pk>/blocage/", views.lot_basculer_blocage, name="lot_basculer_blocage"),
]
