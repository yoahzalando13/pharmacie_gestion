from django.test import TestCase

from pharmacie.outils_tests import creer_lot, creer_medicament, creer_utilisateur
from utilisateurs.permissions import STOCK

from .models import MouvementStock
from .services import ErreurStock, basculer_blocage, corriger_stock, enregistrer_inventaire, enregistrer_mouvement


class ServicesStockTests(TestCase):
    def setUp(self):
        self.user = creer_utilisateur("stock", STOCK)
        self.med = creer_medicament()
        self.lot = creer_lot(self.med, 10, self.user)

    def test_quantite_nulle_ou_negative_refusee(self):
        for q in (0, -3):
            with self.assertRaises(ErreurStock):
                enregistrer_mouvement(self.lot, MouvementStock.Type.SORTIE_VENTE, q, self.user)

    def test_stock_jamais_negatif_rg07(self):
        with self.assertRaises(ErreurStock):
            enregistrer_mouvement(self.lot, MouvementStock.Type.SORTIE_VENTE, 11, self.user)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 10)

    def test_mouvement_trace_avant_apres(self):
        mvt = enregistrer_mouvement(self.lot, MouvementStock.Type.SORTIE_VENTE, 4, self.user)
        self.assertEqual((mvt.stock_avant, mvt.stock_apres), (10, 6))
        self.assertEqual(mvt.utilisateur, self.user)

    def test_correction_motif_obligatoire(self):
        with self.assertRaises(ErreurStock):
            corriger_stock(self.lot.pk, MouvementStock.Type.SORTIE_PERTE, 1, "", self.user)
        corriger_stock(self.lot.pk, MouvementStock.Type.SORTIE_PERTE, 2, "Casse", self.user)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 8)

    def test_inventaire_corrige_les_ecarts(self):
        autre = creer_lot(self.med, 5, self.user)
        mouvements = enregistrer_inventaire({self.lot.pk: 7, autre.pk: 5}, "Inventaire", self.user)
        self.assertEqual(len(mouvements), 1)           # seul l'écart du premier lot
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 7)

    def test_blocage_exclut_le_lot_des_ventes(self):
        with self.assertRaises(ErreurStock):
            basculer_blocage(self.lot.pk, self.user, "")   # motif obligatoire
        basculer_blocage(self.lot.pk, self.user, "Rappel fabricant")
        self.assertEqual(self.med.stock_vendable, 0)
        self.assertEqual(self.med.stock_total, 10)

    def test_lot_perime_non_vendable(self):
        perime = creer_lot(creer_medicament("Autre"), 5, self.user, jours=-1)
        self.assertFalse(perime.est_vendable)
        self.assertTrue(perime.est_perime)
