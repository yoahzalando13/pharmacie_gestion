import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from pharmacie.outils_tests import creer_lot, creer_medicament, creer_utilisateur
from utilisateurs.permissions import ADMIN, PHARMACIEN

from .models import Categorie, Medicament

MEDIA_TEST = tempfile.mkdtemp()


def image_png(taille=(20, 20)):
    tampon = BytesIO()
    Image.new("RGB", taille, "green").save(tampon, "PNG")
    return SimpleUploadedFile("photo.png", tampon.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class MedicamentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_TEST, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.pharmacien = creer_utilisateur("pharma", PHARMACIEN)
        self.client.force_login(self.pharmacien)
        self.categorie = Categorie.objects.create(nom="Vitamines")

    def _donnees(self, **extra):
        d = {"nom": "Vitamine C", "categorie": self.categorie.pk, "forme": "COMPRIME", "dosage": "1 g",
             "prix_achat": "1000", "prix_vente": "1500", "seuil_alerte": "5"}
        d.update(extra)
        return d

    def test_ajouter_un_medicament_avec_photo(self):
        r = self.client.post(reverse("medicament_creer"), self._donnees(photo=image_png()))
        m = Medicament.objects.get()
        self.assertRedirects(r, reverse("medicament_detail", args=[m.pk]))
        self.assertTrue(m.photo.name.startswith("medicaments/"))
        self.assertContains(self.client.get(reverse("medicament_detail", args=[m.pk])), m.photo.url)

    def test_fichier_non_image_refuse(self):
        faux = SimpleUploadedFile("virus.png", b"pas une image", content_type="image/png")
        r = self.client.post(reverse("medicament_creer"), self._donnees(photo=faux))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Medicament.objects.count(), 0)

    def test_prix_de_vente_inferieur_au_prix_achat_refuse(self):
        self.client.post(reverse("medicament_creer"), self._donnees(prix_vente="500"))
        self.assertEqual(Medicament.objects.count(), 0)

    def test_code_barres_unique_rg02(self):
        self.client.post(reverse("medicament_creer"), self._donnees(code_barres="111"))
        self.client.post(reverse("medicament_creer"), self._donnees(nom="Autre", code_barres="111"))
        self.assertEqual(Medicament.objects.count(), 1)
        # Deux médicaments sans code-barres restent possibles
        self.client.post(reverse("medicament_creer"), self._donnees(nom="Sans code 1"))
        self.client.post(reverse("medicament_creer"), self._donnees(nom="Sans code 2"))
        self.assertEqual(Medicament.objects.count(), 3)

    def test_modifier_un_medicament(self):
        m = creer_medicament("Ancien nom")
        self.client.post(reverse("medicament_modifier", args=[m.pk]),
                         self._donnees(nom="Nouveau nom", categorie=m.categorie_id))
        m.refresh_from_db()
        self.assertEqual(m.nom, "Nouveau nom")

    def test_supprimer_avec_historique_archive_le_medicament(self):
        admin = creer_utilisateur("admin", ADMIN)
        self.client.force_login(admin)
        m = creer_medicament()
        creer_lot(m, 3, admin)
        self.client.post(reverse("medicament_supprimer", args=[m.pk]))
        m.refresh_from_db()
        self.assertEqual(m.statut, Medicament.Statut.ARCHIVE)

    def test_categorie_utilisee_non_supprimable(self):
        m = creer_medicament(categorie="Vitamines")
        self.client.post(reverse("categorie_supprimer", args=[m.categorie_id]))
        self.assertTrue(Categorie.objects.filter(pk=m.categorie_id).exists())
