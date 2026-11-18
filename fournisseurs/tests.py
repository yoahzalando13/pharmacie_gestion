from django.test import TestCase
from django.urls import reverse

from achats.models import CommandeAchat
from pharmacie.outils_tests import creer_utilisateur
from utilisateurs.permissions import ADMIN, CAISSIER, STOCK

from .models import Fournisseur


class FournisseurTests(TestCase):
    def setUp(self):
        self.gestionnaire = creer_utilisateur("stock", STOCK)
        self.client.force_login(self.gestionnaire)

    def _donnees(self, **extra):
        d = {"nom": "Pharmad Distribution", "telephone": "020 22 000 01", "email": "",
             "contact_principal": "M. Rasolo", "numero_fiscal": "", "adresse": "Antananarivo"}
        d.update(extra)
        return d

    def test_creer_un_fournisseur(self):
        r = self.client.post(reverse("fournisseur_creer"), self._donnees())
        f = Fournisseur.objects.get()
        self.assertRedirects(r, reverse("fournisseur_detail", args=[f.pk]))
        self.assertEqual(f.cree_par, self.gestionnaire)

    def test_nom_unique(self):
        self.client.post(reverse("fournisseur_creer"), self._donnees())
        r = self.client.post(reverse("fournisseur_creer"), self._donnees(telephone="034 00 000 09"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Fournisseur.objects.count(), 1)

    def test_telephone_obligatoire_et_valide(self):
        for tel in ("", "12-34"):
            self.client.post(reverse("fournisseur_creer"), self._donnees(telephone=tel))
        self.assertEqual(Fournisseur.objects.count(), 0)

    def test_modifier_un_fournisseur(self):
        f = Fournisseur.objects.create(nom="Ancien", telephone="034 00 000 00")
        self.client.post(reverse("fournisseur_modifier", args=[f.pk]), self._donnees(nom="Nouveau"))
        f.refresh_from_db()
        self.assertEqual(f.nom, "Nouveau")

    def test_desactiver_puis_reactiver(self):
        f = Fournisseur.objects.create(nom="Medi-Import", telephone="034 00 000 02")
        url = reverse("fournisseur_basculer_actif", args=[f.pk])
        self.client.post(url)
        f.refresh_from_db()
        self.assertFalse(f.actif)
        self.client.post(url)
        f.refresh_from_db()
        self.assertTrue(f.actif)

    def test_suppression_avec_commande_desactive_le_fournisseur(self):
        f = Fournisseur.objects.create(nom="Avec commande", telephone="034 00 000 03")
        CommandeAchat.objects.create(fournisseur=f, cree_par=self.gestionnaire)
        self.client.force_login(creer_utilisateur("admin", ADMIN))
        self.client.post(reverse("fournisseur_supprimer", args=[f.pk]))
        f.refresh_from_db()
        self.assertFalse(f.actif)

    def test_suppression_sans_historique(self):
        f = Fournisseur.objects.create(nom="Inutile", telephone="034 00 000 04")
        self.client.force_login(creer_utilisateur("admin", ADMIN))
        self.client.post(reverse("fournisseur_supprimer", args=[f.pk]))
        self.assertFalse(Fournisseur.objects.filter(pk=f.pk).exists())

    def test_caissier_sans_acces_rg11(self):
        self.client.force_login(creer_utilisateur("caisse", CAISSIER))
        self.assertEqual(self.client.get(reverse("fournisseur_liste")).status_code, 403)
