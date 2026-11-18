from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from utilisateurs.models import JournalAudit
from utilisateurs.permissions import CAISSIER, GESTION, PHARMACIEN, STOCK, role_requis

from .forms import CategorieForm, MedicamentForm
from .models import Categorie, Medicament

TRIS = [
    ("nom", "Nom (A → Z)"),
    ("-nom", "Nom (Z → A)"),
    ("prix", "Prix croissant"),
    ("-prix", "Prix décroissant"),
    ("recent", "Plus récents"),
]
TRIS_SQL = {"nom": "nom", "-nom": "-nom", "prix": "prix_vente", "-prix": "-prix_vente", "recent": "-date_creation"}


# ---------------------------------------------------------------- MÉDICAMENTS

@role_requis(PHARMACIEN, STOCK, CAISSIER, GESTION)
def medicament_liste(request):
    medicaments = Medicament.objects.select_related("categorie")

    # Recherche par nom, DCI ou code-barres
    q = request.GET.get("q", "").strip()
    if q:
        medicaments = medicaments.filter(
            Q(nom__icontains=q) | Q(dci__icontains=q) | Q(code_barres=q)
        )

    # Filtre par catégorie
    categorie_id = request.GET.get("categorie", "")
    if categorie_id.isdigit():
        medicaments = medicaments.filter(categorie_id=categorie_id)

    # Filtre par statut (actifs par défaut, "" = tous)
    statut = request.GET.get("statut", Medicament.Statut.ACTIF)
    if statut in Medicament.Statut.values:
        medicaments = medicaments.filter(statut=statut)

    # Tri
    tri = request.GET.get("tri", "nom")
    medicaments = medicaments.order_by(TRIS_SQL.get(tri, "nom"))

    # Pagination : 10 médicaments par page
    page = Paginator(medicaments, 10).get_page(request.GET.get("page"))

    # On garde les filtres dans les liens de pagination
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "medicaments/medicament_liste.html", {
        "page": page,
        "categories": Categorie.objects.all(),
        "q": q,
        "categorie_id": categorie_id,
        "statut": statut,
        "tri": tri,
        "tris": TRIS,
        "params": params.urlencode(),
    })


@role_requis(PHARMACIEN, STOCK, CAISSIER, GESTION)
def medicament_detail(request, pk):
    medicament = get_object_or_404(Medicament.objects.select_related("categorie", "cree_par"), pk=pk)
    return render(request, "medicaments/medicament_detail.html", {"m": medicament})


@role_requis(PHARMACIEN)
def medicament_creer(request):
    if request.method == "POST":
        form = MedicamentForm(request.POST, request.FILES)
        if form.is_valid():
            medicament = form.save(commit=False)
            medicament.cree_par = request.user
            medicament.save()
            JournalAudit.enregistrer(request.user, "CREATION", f"Médicament #{medicament.pk}", str(medicament))
            messages.success(request, f"« {medicament} » a été ajouté.")
            return redirect("medicament_detail", pk=medicament.pk)
    else:
        form = MedicamentForm()

    return render(request, "formulaire.html", {
    "form": form,
    "titre": "Ajouter un médicament",
    "url_retour": reverse("medicament_liste"),
})


@role_requis(PHARMACIEN)
def medicament_modifier(request, pk):
    medicament = get_object_or_404(Medicament, pk=pk)
    if request.method == "POST":
        form = MedicamentForm(request.POST, request.FILES, instance=medicament)
        if form.is_valid():
            form.save()
            champs = ", ".join(form.changed_data) or "aucun"
            JournalAudit.enregistrer(request.user, "MODIFICATION", f"Médicament #{pk}", f"Champs modifiés : {champs}")
            messages.success(request, f"« {medicament} » a été modifié.")
            return redirect("medicament_detail", pk=pk)
    else:
        form = MedicamentForm(instance=medicament)

    return render(request, "formulaire.html", {
        "form": form,
        "titre": f"Modifier « {medicament} »",
        "url_retour": reverse("medicament_detail", args=[pk]),
    })


@role_requis(PHARMACIEN)
@require_POST
def medicament_basculer_statut(request, pk):
    """Archive un médicament actif, ou réactive un médicament archivé."""
    medicament = get_object_or_404(Medicament, pk=pk)
    if medicament.statut == Medicament.Statut.ACTIF:
        medicament.statut = Medicament.Statut.ARCHIVE
        action, texte = "ARCHIVAGE", "archivé"
    else:
        medicament.statut = Medicament.Statut.ACTIF
        action, texte = "REACTIVATION", "réactivé"
    medicament.save(update_fields=["statut"])
    JournalAudit.enregistrer(request.user, action, f"Médicament #{pk}", str(medicament))
    messages.success(request, f"« {medicament} » a été {texte}.")
    return redirect("medicament_detail", pk=pk)


@role_requis()   # sans argument = administrateur uniquement
def medicament_supprimer(request, pk):
    medicament = get_object_or_404(Medicament, pk=pk)

    if request.method == "POST":
        nom = str(medicament)
        try:
            medicament.delete()
        except ProtectedError:
            # Le médicament a un historique (lots, ventes...) : on archive au lieu de supprimer
            medicament.statut = Medicament.Statut.ARCHIVE
            medicament.save(update_fields=["statut"])
            JournalAudit.enregistrer(request.user, "ARCHIVAGE", f"Médicament #{pk}", "Suppression refusée : historique existant")
            messages.warning(request, f"« {nom} » possède un historique : il a été archivé au lieu d'être supprimé.")
            return redirect("medicament_detail", pk=pk)

        if medicament.photo:
            medicament.photo.delete(save=False)   # supprime aussi le fichier image
        JournalAudit.enregistrer(request.user, "SUPPRESSION", f"Médicament #{pk}", nom)
        messages.success(request, f"« {nom} » a été supprimé.")
        return redirect("medicament_liste")

    return render(request, "confirmer_suppression.html", {
        "titre": f"Supprimer « {medicament} » ?",
        "message": "S'il possède déjà un historique, il sera archivé au lieu d'être supprimé.",
        "url_retour": reverse("medicament_detail", args=[pk]),
    })


# ---------------------------------------------------------------- CATÉGORIES

@role_requis(PHARMACIEN, STOCK, GESTION)
def categorie_liste(request):
    categories = Categorie.objects.annotate(nb_medicaments=Count("medicaments")).order_by("nom")
    q = request.GET.get("q", "").strip()
    if q:
        categories = categories.filter(nom__icontains=q)
    page = Paginator(categories, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "medicaments/categorie_liste.html", {
        "page": page, "q": q, "params": params.urlencode(),
    })


@role_requis(PHARMACIEN)
def categorie_creer(request):
    form = CategorieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        categorie = form.save()
        JournalAudit.enregistrer(request.user, "CREATION", f"Catégorie #{categorie.pk}", categorie.nom)
        messages.success(request, f"Catégorie « {categorie} » ajoutée.")
        return redirect("categorie_liste")
    return render(request, "formulaire.html", {
        "form": form, "titre": "Ajouter une catégorie", "url_retour": reverse("categorie_liste"),
    })


@role_requis(PHARMACIEN)
def categorie_modifier(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    form = CategorieForm(request.POST or None, instance=categorie)
    if request.method == "POST" and form.is_valid():
        form.save()
        JournalAudit.enregistrer(request.user, "MODIFICATION", f"Catégorie #{pk}", categorie.nom)
        messages.success(request, f"Catégorie « {categorie} » modifiée.")
        return redirect("categorie_liste")
    return render(request, "formulaire.html", {
        "form": form, "titre": f"Modifier « {categorie} »", "url_retour": reverse("categorie_liste"),
    })


@role_requis(PHARMACIEN)
def categorie_supprimer(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == "POST":
        try:
            categorie.delete()
        except ProtectedError:
            messages.error(request, f"Impossible de supprimer « {categorie} » : des médicaments l'utilisent.")
            return redirect("categorie_liste")
        JournalAudit.enregistrer(request.user, "SUPPRESSION", f"Catégorie #{pk}", categorie.nom)
        messages.success(request, f"Catégorie « {categorie} » supprimée.")
        return redirect("categorie_liste")
    return render(request, "confirmer_suppression.html", {
        "titre": f"Supprimer la catégorie « {categorie} » ?",
        "message": "Cette action est définitive.",
        "url_retour": reverse("categorie_liste"),
    })