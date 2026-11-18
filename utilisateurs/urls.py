from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # Connexion / déconnexion
    path(
        "connexion/",
        auth_views.LoginView.as_view(
            template_name="utilisateurs/connexion.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),

    # Mon compte
    path("mot-de-passe/", views.mot_de_passe_changer, name="mot_de_passe_changer"),

    # Gestion des utilisateurs (administrateur)
    path("utilisateurs/", views.utilisateur_liste, name="utilisateur_liste"),
    path("utilisateurs/ajouter/", views.utilisateur_creer, name="utilisateur_creer"),
    path("utilisateurs/<int:pk>/modifier/", views.utilisateur_modifier, name="utilisateur_modifier"),
    path("utilisateurs/<int:pk>/statut/", views.utilisateur_basculer_actif, name="utilisateur_basculer_actif"),
    path("utilisateurs/<int:pk>/mot-de-passe/", views.utilisateur_reinitialiser_mdp, name="utilisateur_reinitialiser_mdp"),

    # Journal d'audit
    path("journal/", views.journal_liste, name="journal_liste"),
]