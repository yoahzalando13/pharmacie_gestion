from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from pharmacie.outils_tests import creer_utilisateur
from utilisateurs.permissions import GESTION


class RapportsTests(TestCase):
    def setUp(self):
        call_command("donnees_demo", stdout=StringIO())
        self.client.force_login(creer_utilisateur("resp", GESTION))

    def test_tableau_de_bord_et_rapports(self):
        for url in (reverse("tableau_de_bord"), reverse("tableau_de_bord") + "?jours=30",
                    reverse("rapports"), reverse("rapports") + "?du=2020-01-01&au=2030-12-31"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.get(reverse("tableau_de_bord"))
        self.assertGreater(r.context["kpi"]["medicaments_actifs"], 0)
        self.assertGreater(r.context["kpi"]["stocks_faibles"], 0)
        self.assertGreater(r.context["kpi"]["perimes"], 0)

    def test_rapports_pdf(self):
        for nom in ("pdf_stock", "pdf_ventes", "pdf_achats", "pdf_peremptions"):
            r = self.client.get(reverse(nom))
            self.assertEqual(r.status_code, 200, nom)
            self.assertTrue(r.content.startswith(b"%PDF"), nom)

    def test_chiffre_affaires_distinct_de_la_marge(self):
        stats = self.client.get(reverse("rapports")).context["stats"]
        self.assertGreater(stats["chiffre_affaires"], stats["marge"])
        self.assertLess(stats["encaissements"], stats["chiffre_affaires"])   # mobile money en attente
