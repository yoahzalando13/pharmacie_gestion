import threading
from decimal import Decimal

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from medicaments.models import Medicament
from pharmacie.outils_tests import creer_lot, creer_medicament, creer_utilisateur, jeton
from stock.models import LotStock, MouvementStock
from stock.services import ErreurStock
from utilisateurs.permissions import CAISSIER, GESTION, PHARMACIEN, STOCK

from .models import ModePaiement, Paiement, Vente
from .services import VenteDejaEnregistree, annuler_vente, enregistrer_retour, valider_vente, verifier_paiement


def article(med, quantite, lot=None):
    return {"medicament_id": med.pk, "lot_id": lot.pk if lot else None, "quantite": quantite}


class VentesTests(TestCase):
    def setUp(self):
        self.caissier = creer_utilisateur("caissier", CAISSIER)
        self.med = creer_medicament(prix_vente="2500")
        self.lot = creer_lot(self.med, 20, self.caissier, jours=200, numero="B")

    def test_vendre_3_unites_diminue_le_stock_de_3_une_seule_fois_rg06(self):
        j = jeton()
        vente = valider_vente([article(self.med, 3)], self.caissier, j)
        self.assertEqual(self.med.stock_total, 17)
        self.assertEqual(vente.total, Decimal("7500"))
        with self.assertRaises(VenteDejaEnregistree):
            valider_vente([article(self.med, 3)], self.caissier, j)
        self.assertEqual(self.med.stock_total, 17)
        self.assertEqual(Vente.objects.count(), 1)

    def test_vendre_plus_que_le_stock_refuse(self):
        with self.assertRaises(ErreurStock):
            valider_vente([article(self.med, 21)], self.caissier, jeton())
        self.assertEqual(self.med.stock_total, 20)
        self.assertEqual(Vente.objects.count(), 0)          # transaction atomique : rien n'est enregistré

    def test_quantite_nulle_ou_negative_refusee(self):
        for q in (0, -1):
            with self.assertRaises(ErreurStock):
                valider_vente([article(self.med, q)], self.caissier, jeton())

    def test_vendre_un_lot_perime_refuse_rg08(self):
        perime = creer_lot(self.med, 5, self.caissier, jours=-2, numero="P")
        with self.assertRaises(ErreurStock):
            valider_vente([article(self.med, 1, perime)], self.caissier, jeton())

    def test_vendre_un_lot_bloque_refuse_rg08(self):
        bloque = creer_lot(self.med, 5, self.caissier, numero="X", bloque=True)
        with self.assertRaises(ErreurStock):
            valider_vente([article(self.med, 1, bloque)], self.caissier, jeton())

    def test_fefo_sort_le_lot_qui_perime_en_premier(self):
        proche = creer_lot(self.med, 4, self.caissier, jours=30, numero="A")
        creer_lot(self.med, 5, self.caissier, jours=-1, numero="PERIME")     # jamais choisi
        vente = valider_vente([article(self.med, 6)], self.caissier, jeton())
        repartition = {l.lot.numero_lot: l.quantite for l in vente.lignes.select_related("lot")}
        self.assertEqual(repartition, {"A": 4, "B": 2})
        proche.refresh_from_db()
        self.assertEqual(proche.quantite, 0)

    def test_prix_fige_au_moment_de_la_vente_rg12(self):
        vente = valider_vente([article(self.med, 2)], self.caissier, jeton())
        Medicament.objects.filter(pk=self.med.pk).update(prix_vente=Decimal("9999"))
        ligne = vente.lignes.get()
        self.assertEqual(ligne.prix_unitaire, Decimal("2500"))
        vente.refresh_from_db()
        self.assertEqual(vente.total, Decimal("5000"))

    def test_vendeur_enregistre_et_journalise(self):
        vente = valider_vente([article(self.med, 1)], self.caissier, jeton())
        self.assertEqual(vente.vendeur, self.caissier)
        self.assertTrue(self.caissier.actions_journal.filter(action="VENTE").exists())

    def test_especes_insuffisantes_refusees(self):
        with self.assertRaises(ErreurStock):
            valider_vente([article(self.med, 2)], self.caissier, jeton(), montant_recu=Decimal("1000"))

    def test_mobile_money_en_attente_puis_confirme(self):
        vente = valider_vente([article(self.med, 1)], self.caissier, jeton(), mode=ModePaiement.MOBILE_MONEY)
        paiement = vente.paiements.get()
        self.assertEqual(paiement.statut, Paiement.Statut.EN_ATTENTE)
        with self.assertRaises(ErreurStock):
            verifier_paiement(paiement.pk, self.caissier, True)              # référence obligatoire
        verifier_paiement(paiement.pk, self.caissier, True, "MVOLA-42")
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, Paiement.Statut.CONFIRME)

    def test_retour_partiel_avec_remise_en_stock(self):
        vente = valider_vente([article(self.med, 5)], self.caissier, jeton())
        ligne = vente.lignes.get()
        retour = enregistrer_retour(ligne.pk, 2, "Erreur de produit", True, self.caissier)
        self.assertEqual(retour.montant_rembourse, Decimal("5000"))
        self.assertEqual(self.med.stock_total, 17)
        with self.assertRaises(ErreurStock):
            enregistrer_retour(ligne.pk, 4, "Trop", False, self.caissier)      # 3 retournables seulement
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)                 # la vente d'origine reste

    def test_retour_sans_remise_en_stock(self):
        vente = valider_vente([article(self.med, 2)], self.caissier, jeton())
        enregistrer_retour(vente.lignes.get().pk, 1, "Produit ouvert", False, self.caissier)
        self.assertEqual(self.med.stock_total, 18)

    def test_annulation_compensatoire_rg10(self):
        pharmacien = creer_utilisateur("pharma", PHARMACIEN)
        vente = valider_vente([article(self.med, 4)], self.caissier, jeton())
        annuler_vente(vente.pk, pharmacien, "Erreur de saisie")
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)
        self.assertEqual(self.med.stock_total, 20)
        self.assertTrue(MouvementStock.objects.filter(type=MouvementStock.Type.RETOUR_CLIENT).exists())
        with self.assertRaises(ErreurStock):
            annuler_vente(vente.pk, pharmacien, "Encore")


class CaisseVueTests(TestCase):
    def setUp(self):
        self.caissier = creer_utilisateur("caissier", CAISSIER)
        self.med = creer_medicament(code_barres="1234567890123")
        creer_lot(self.med, 10, self.caissier)
        self.client.force_login(self.caissier)

    def test_parcours_complet_de_caisse(self):
        url = reverse("caisse")
        r = self.client.get(url, {"q": "1234567890123"})                      # scan du code-barres
        self.assertRedirects(r, url)
        self.client.post(url, {"action": "modifier", "index": 0, "quantite": 3, "lot_id": ""})
        page = self.client.get(url)
        self.assertContains(page, "Confirmer la vente")
        j = page.context["jeton"]
        r = self.client.post(url, {"action": "valider", "jeton": j, "mode": "ESPECES", "montant_recu": "10000"})
        vente = Vente.objects.get()
        self.assertRedirects(r, reverse("vente_detail", args=[vente.pk]))
        self.assertEqual(self.med.stock_total, 7)
        # Double clic : le même formulaire renvoyé ne crée pas de deuxième vente
        self.client.post(url, {"action": "ajouter", "medicament_id": self.med.pk, "quantite": 3})
        self.client.post(url, {"action": "valider", "jeton": j, "mode": "ESPECES"})
        self.assertEqual(Vente.objects.count(), 1)
        self.assertEqual(self.med.stock_total, 7)

    def test_recu_pdf_lisible_avec_bon_total(self):
        vente = valider_vente([article(self.med, 2)], self.caissier, jeton())
        for nom in ("pdf_recu", "pdf_facture"):
            r = self.client.get(reverse(nom, args=[vente.pk]))
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.startswith(b"%PDF"))

    def test_gestionnaire_de_stock_sans_acces_caisse_rg11(self):
        self.client.force_login(creer_utilisateur("stock", STOCK))
        self.assertEqual(self.client.get(reverse("caisse")).status_code, 403)
        self.assertEqual(self.client.get(reverse("vente_liste")).status_code, 403)

    def test_responsable_gestion_consulte_sans_vendre(self):
        self.client.force_login(creer_utilisateur("gestion", GESTION))
        self.assertEqual(self.client.get(reverse("vente_liste")).status_code, 200)
        self.assertEqual(self.client.get(reverse("caisse")).status_code, 403)


@skipUnlessDBFeature("has_select_for_update")
class VentesSimultaneesTests(TransactionTestCase):
    """Deux validations simultanées : aucune sortie en double ni stock négatif (§9). PostgreSQL uniquement."""

    def test_deux_validations_simultanees(self):
        caissier = creer_utilisateur("c", CAISSIER)
        med = creer_medicament()
        lot = creer_lot(med, 5, caissier)
        erreurs = []

        def vendre():
            try:
                valider_vente([article(med, 4)], caissier, jeton())
            except ErreurStock as e:
                erreurs.append(e)
            finally:
                close_old_connections()

        fils = [threading.Thread(target=vendre) for _ in range(2)]
        [f.start() for f in fils]
        [f.join() for f in fils]
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 1)
        self.assertEqual(len(erreurs), 1)
        self.assertEqual(LotStock.objects.filter(quantite__lt=0).count(), 0)
