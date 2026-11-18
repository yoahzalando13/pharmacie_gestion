from django.test import TestCase
from django.urls import reverse

from pharmacie.outils_tests import creer_utilisateur
from utilisateurs.models import JournalAudit, Utilisateur
from utilisateurs.permissions import ADMIN, CAISSIER, GESTION, PHARMACIEN, STOCK


class PermissionsTests(TestCase):
    def test_page_protegee_sans_connexion(self):
        r = self.client.get(reverse("medicament_liste"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_acces_sans_permission_interdit_rg11(self):
        self.client.force_login(creer_utilisateur("caisse", CAISSIER))
        for nom in ("utilisateur_liste", "journal_liste", "rapports", "inventaire", "commande_creer", "medicament_creer"):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 403, nom)

    def test_administrateur_gere_les_utilisateurs(self):
        self.client.force_login(creer_utilisateur("admin", ADMIN))
        self.assertEqual(self.client.get(reverse("utilisateur_liste")).status_code, 200)

    def test_connexion_journalisee(self):
        creer_utilisateur("pharma", PHARMACIEN, mot_de_passe="Mdp-Test-2026")
        self.client.post(reverse("login"), {"username": "pharma", "password": "Mdp-Test-2026"})
        self.assertTrue(JournalAudit.objects.filter(action="CONNEXION").exists())

    def test_mot_de_passe_jamais_stocke_en_clair(self):
        u = creer_utilisateur("x", STOCK, mot_de_passe="Secret-123456")
        self.assertNotEqual(u.password, "Secret-123456")
        self.assertTrue(u.check_password("Secret-123456"))


class PagesParRoleTests(TestCase):
    """Chaque rôle peut ouvrir les pages de son menu sans erreur."""

    PAGES = {
        PHARMACIEN: ["tableau_de_bord", "medicament_liste", "fournisseur_liste", "client_liste", "commande_liste",
                     "stock_liste", "stock_alertes", "mouvement_liste", "inventaire", "caisse", "vente_liste", "rapports"],
        STOCK: ["tableau_de_bord", "medicament_liste", "fournisseur_liste", "commande_liste", "stock_liste",
                "stock_alertes", "mouvement_liste", "inventaire"],
        CAISSIER: ["tableau_de_bord", "medicament_liste", "client_liste", "stock_liste", "caisse", "vente_liste"],
        GESTION: ["tableau_de_bord", "medicament_liste", "fournisseur_liste", "client_liste", "commande_liste",
                  "stock_liste", "stock_alertes", "vente_liste", "rapports"],
        ADMIN: ["tableau_de_bord", "utilisateur_liste", "journal_liste", "rapports", "caisse"],
    }

    def test_pages_du_menu(self):
        for role, pages in self.PAGES.items():
            self.client.force_login(creer_utilisateur(role.replace(" ", "_"), role))
            for nom in pages:
                r = self.client.get(reverse(nom))
                self.assertEqual(r.status_code, 200, f"{role} → {nom}")


class GestionUtilisateursTests(TestCase):
    def setUp(self):
        self.admin = creer_utilisateur("admin", ADMIN)
        self.client.force_login(self.admin)

    def test_administrateur_cree_un_compte_avec_un_role(self):
        from django.contrib.auth.models import Group
        caissier = Group.objects.get(name=CAISSIER)
        r = self.client.post(reverse("utilisateur_creer"), {
            "username": "nouveau", "first_name": "Miora", "last_name": "Andria", "email": "",
            "telephone": "", "password1": "Tres-Long-Mdp-2026", "password2": "Tres-Long-Mdp-2026",
            "roles": [caissier.pk],
        })
        self.assertRedirects(r, reverse("utilisateur_liste"))
        u = Utilisateur.objects.get(username="nouveau")
        self.assertTrue(u.groups.filter(name=CAISSIER).exists())
        self.assertTrue(JournalAudit.objects.filter(action="CREATION", objet="Utilisateur nouveau").exists())

    def test_desactiver_un_compte_empeche_la_connexion(self):
        u = creer_utilisateur("ancien", CAISSIER, mot_de_passe="Mdp-Test-2026")
        self.client.post(reverse("utilisateur_basculer_actif", args=[u.pk]))
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username="ancien", password="Mdp-Test-2026"))

    def test_administrateur_simple_ne_modifie_pas_un_super_administrateur(self):
        root = Utilisateur.objects.create_superuser("root", password="Mdp-Test-2026")
        self.assertEqual(self.client.get(reverse("utilisateur_modifier", args=[root.pk])).status_code, 403)
