from django.urls import path

from . import views

urlpatterns = [
    path("", views.rapports, name="rapports"),
    path("pdf/stock/", views.pdf_stock, name="pdf_stock"),
    path("pdf/ventes/", views.pdf_ventes, name="pdf_ventes"),
    path("pdf/achats/", views.pdf_achats, name="pdf_achats"),
    path("pdf/peremptions/", views.pdf_peremptions, name="pdf_peremptions"),
    path("pdf/recu/<int:pk>/", views.pdf_recu, name="pdf_recu"),
    path("pdf/facture/<int:pk>/", views.pdf_facture, name="pdf_facture"),
    path("pdf/bon-commande/<int:pk>/", views.pdf_bon_commande, name="pdf_bon_commande"),
    path("pdf/bon-reception/<int:pk>/", views.pdf_bon_reception, name="pdf_bon_reception"),
]
