from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pharmacie.outils_tests import creer_medicament, creer_utilisateur, jeton
from fournisseurs.models import Fournisseur
from stock.models import LotStock
from stock.services import ErreurStock
from utilisateurs.permissions import CAISSIER, STOCK

from .models import CommandeAchat, LigneAchat
from .services import ReceptionDejaEnregistree, annuler_commande, receptionner, valider_commande


class AchatsTests(TestCase):
    def setUp(self):
        self.user = creer_utilisateur("stock", STOCK)
        self.med = creer_medicament()
        self.fournisseur = Fournisseur.objects.create(nom="Fournisseur test", telephone="034 00 000 00")
        self.commande = CommandeAchat.objects.create(fournisseur=self.fournisseur, cree_par=self.user)
        self.ligne = LigneAchat.objects.create(
            commande=self.commande, medicament=self.med, quantite_commandee=20, prix_achat=self.med.prix_achat,
        )

    def _saisie(self, quantite, numero="LOT-A", jours=300):
        return [{"ligne_id": self.ligne.pk, "quantite": quantite, "numero_lot": numero,
                 "date_peremption": timezone.localdate() + timedelta(days=jours)}]

    def test_commande_ne_modifie_pas_le_stock_rg04(self):
        valider_commande(self.commande.pk, self.user)
        self.assertEqual(self.med.stock_total, 0)

    def test_reception_de_20_unites_une_seule_fois_rg05(self):
        valider_commande(self.commande.pk, self.user)
        j = jeton()
        receptionner(self.commande.pk, self._saisie(20), self.user, j)
        self.assertEqual(self.med.stock_total, 20)
        with self.assertRaises((ReceptionDejaEnregistree, ErreurStock)):
            receptionner(self.commande.pk, self._saisie(20), self.user, j)   # double envoi
        self.assertEqual(self.med.stock_total, 20)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, CommandeAchat.Statut.RECUE)

    def test_reception_partielle(self):
        valider_commande(self.commande.pk, self.user)
        receptionner(self.commande.pk, self._saisie(8), self.user, jeton())
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, CommandeAchat.Statut.PARTIELLE)
        with self.assertRaises(ErreurStock):
            receptionner(self.commande.pk, self._saisie(13), self.user, jeton())   # 12 restants seulement

    def test_brouillon_non_receptionnable(self):
        with self.assertRaises(ErreurStock):
            receptionner(self.commande.pk, self._saisie(5), self.user, jeton())

    def test_annulation_impossible_apres_reception(self):
        valider_commande(self.commande.pk, self.user)
        receptionner(self.commande.pk, self._saisie(5), self.user, jeton())
        with self.assertRaises(ErreurStock):
            annuler_commande(self.commande.pk, self.user)

    def test_lot_existant_avec_autre_date_refuse(self):
        valider_commande(self.commande.pk, self.user)
        receptionner(self.commande.pk, self._saisie(5, jours=300), self.user, jeton())
        with self.assertRaises(ErreurStock):
            receptionner(self.commande.pk, self._saisie(5, jours=200), self.user, jeton())
        self.assertEqual(LotStock.objects.count(), 1)

    def test_pages_et_bons_pdf(self):
        self.client.force_login(self.user)
        valider_commande(self.commande.pk, self.user)
        reception = receptionner(self.commande.pk, self._saisie(20), self.user, jeton())
        for url in (reverse("commande_liste"), reverse("commande_detail", args=[self.commande.pk]),
                    reverse("reception_detail", args=[reception.pk])):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.get(reverse("pdf_bon_commande", args=[self.commande.pk]))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        r = self.client.get(reverse("pdf_bon_reception", args=[reception.pk]))
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_caissier_sans_acces_aux_achats_rg11(self):
        self.client.force_login(creer_utilisateur("caisse", CAISSIER))
        self.assertEqual(self.client.get(reverse("commande_liste")).status_code, 403)
