from django.test import TestCase
from django.urls import reverse

from pharmacie.outils_tests import creer_lot, creer_medicament, creer_utilisateur, jeton
from utilisateurs.models import JournalAudit
from utilisateurs.permissions import ADMIN, CAISSIER, STOCK
from ventes.services import valider_vente

from .models import Client


class ClientTests(TestCase):
    def setUp(self):
        self.caissier = creer_utilisateur("caissier", CAISSIER)
        self.client.force_login(self.caissier)

    def _donnees(self, **extra):
        d = {"nom": "Rasoa Hanta", "telephone": "034 12 345 67", "email": "", "adresse": "Antananarivo"}
        d.update(extra)
        return d

    def test_creer_un_client(self):
        r = self.client.post(reverse("client_creer"), self._donnees())
        c = Client.objects.get()
        self.assertRedirects(r, reverse("client_detail", args=[c.pk]))
        self.assertEqual(c.cree_par, self.caissier)
        self.assertTrue(JournalAudit.objects.filter(action="CREATION", objet=f"Client #{c.pk}").exists())

    def test_telephone_invalide_refuse(self):
        r = self.client.post(reverse("client_creer"), self._donnees(telephone="abc"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Client.objects.count(), 0)

    def test_modifier_un_client(self):
        c = Client.objects.create(nom="Ancien nom")
        self.client.post(reverse("client_modifier", args=[c.pk]), self._donnees(nom="Nouveau nom"))
        c.refresh_from_db()
        self.assertEqual(c.nom, "Nouveau nom")

    def test_recherche_par_telephone_sans_espaces(self):
        Client.objects.create(nom="Rakoto Be", telephone="034 12 345 67")
        r = self.client.get(reverse("client_liste"), {"q": "0341234567"})
        self.assertContains(r, "Rakoto Be")

    def test_suppression_sans_historique(self):
        self.client.force_login(creer_utilisateur("admin", ADMIN))
        c = Client.objects.create(nom="Sans achat")
        self.client.post(reverse("client_supprimer", args=[c.pk]))
        self.assertFalse(Client.objects.filter(pk=c.pk).exists())

    def test_suppression_avec_ventes_desactive_le_client(self):
        med = creer_medicament()
        creer_lot(med, 5, self.caissier)
        c = Client.objects.create(nom="Client fidèle")
        valider_vente([{"medicament_id": med.pk, "lot_id": None, "quantite": 1}],
                      self.caissier, jeton(), client=c)
        self.client.force_login(creer_utilisateur("admin", ADMIN))
        self.client.post(reverse("client_supprimer", args=[c.pk]))
        c.refresh_from_db()
        self.assertFalse(c.actif)

    def test_caissier_ne_supprime_pas(self):
        c = Client.objects.create(nom="Protégé")
        self.assertEqual(self.client.post(reverse("client_supprimer", args=[c.pk])).status_code, 403)
        self.assertTrue(Client.objects.filter(pk=c.pk).exists())

    def test_gestionnaire_de_stock_sans_acces_rg11(self):
        self.client.force_login(creer_utilisateur("stock", STOCK))
        self.assertEqual(self.client.get(reverse("client_liste")).status_code, 403)
