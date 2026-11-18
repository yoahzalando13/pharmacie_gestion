"""Fabriques de données partagées par les tests automatisés."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.utils import timezone

from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from stock.services import enregistrer_mouvement
from utilisateurs.models import Utilisateur
from utilisateurs.permissions import TOUS_LES_ROLES


def creer_roles():
    for nom in TOUS_LES_ROLES:
        Group.objects.get_or_create(name=nom)


def creer_utilisateur(username, *roles, mot_de_passe="Mdp-Test-2026"):
    creer_roles()
    u = Utilisateur.objects.create_user(username, password=mot_de_passe)
    for r in roles:
        u.groups.add(Group.objects.get(name=r))
    return u


def creer_medicament(nom="Doliprane", prix_achat="1000", prix_vente="2000", seuil=5, **kwargs):
    categorie, _ = Categorie.objects.get_or_create(nom=kwargs.pop("categorie", "Antalgiques"))
    return Medicament.objects.create(
        nom=nom, categorie=categorie, prix_achat=Decimal(prix_achat), prix_vente=Decimal(prix_vente),
        seuil_alerte=seuil, **kwargs,
    )


def creer_lot(medicament, quantite, utilisateur, jours=365, numero=None, bloque=False):
    lot = LotStock.objects.create(
        medicament=medicament, numero_lot=numero or f"LOT-{uuid.uuid4().hex[:6]}",
        date_peremption=timezone.localdate() + timedelta(days=jours), bloque=bloque,
    )
    if quantite:
        enregistrer_mouvement(lot, MouvementStock.Type.CORRECTION_PLUS, quantite, utilisateur, motif="Stock de test")
    lot.refresh_from_db()
    return lot


def jeton():
    return uuid.uuid4().hex
