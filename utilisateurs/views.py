from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import (
    ChangementMotDePasseForm,
    ReinitialisationMotDePasseForm,
    UtilisateurCreationForm,
    UtilisateurModificationForm,
)
from .models import JournalAudit, Utilisateur
from .permissions import TOUS_LES_ROLES, role_requis


# ---------------------------------------------------------------- Outils

def _verifier_droits(request, cible):
    """Un administrateur simple ne peut pas modifier un super-administrateur."""
    if cible.is_superuser and not request.user.is_superuser:
        raise PermissionDenied


def _params_sans_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _lire_date(valeur):
    try:
        return parse_date(valeur or "")
    except ValueError:
        return None


# ---------------------------------------------------------------- Utilisateurs

@role_requis()   # administrateur uniquement
def utilisateur_liste(request):
    utilisateurs = Utilisateur.objects.prefetch_related("groups").order_by("username")

    q = request.GET.get("q", "").strip()
    if q:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(telephone__icontains=q)
        )

    role = request.GET.get("role", "")
    if role in TOUS_LES_ROLES:
        utilisateurs = utilisateurs.filter(groups__name=role)

    etat = request.GET.get("etat", "")
    if etat == "actifs":
        utilisateurs = utilisateurs.filter(is_active=True)
    elif etat == "inactifs":
        utilisateurs = utilisateurs.filter(is_active=False)

    page = Paginator(utilisateurs, 15).get_page(request.GET.get("page"))
    return render(request, "utilisateurs/utilisateur_liste.html", {
        "page": page,
        "q": q,
        "role": role,
        "etat": etat,
        "roles": TOUS_LES_ROLES,
        "params": _params_sans_page(request),
    })


@role_requis()
def utilisateur_creer(request):
    form = UtilisateurCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        nouveau = form.save()
        roles = ", ".join(g.name for g in nouveau.groups.all()) or "aucun"
        JournalAudit.enregistrer(request.user, "CREATION", f"Utilisateur {nouveau.username}", f"Rôles : {roles}")
        messages.success(request, f"Le compte « {nouveau.username} » a été créé.")
        return redirect("utilisateur_liste")

    return render(request, "formulaire.html", {
        "form": form,
        "titre": "Créer un utilisateur",
        "url_retour": reverse("utilisateur_liste"),
    })


@role_requis()
def utilisateur_modifier(request, pk):
    cible = get_object_or_404(Utilisateur, pk=pk)
    _verifier_droits(request, cible)

    form = UtilisateurModificationForm(
        request.POST or None, instance=cible, utilisateur_connecte=request.user
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        champs = ", ".join(form.changed_data) or "aucun"
        JournalAudit.enregistrer(request.user, "MODIFICATION", f"Utilisateur {cible.username}", f"Champs modifiés : {champs}")
        messages.success(request, f"Le compte « {cible.username} » a été modifié.")
        return redirect("utilisateur_liste")

    return render(request, "formulaire.html", {
        "form": form,
        "titre": f"Modifier « {cible.username} »",
        "url_retour": reverse("utilisateur_liste"),
    })


@role_requis()
@require_POST
def utilisateur_basculer_actif(request, pk):
    cible = get_object_or_404(Utilisateur, pk=pk)
    _verifier_droits(request, cible)

    if cible.pk == request.user.pk:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect("utilisateur_liste")

    cible.is_active = not cible.is_active
    cible.save(update_fields=["is_active"])
    action = "ACTIVATION" if cible.is_active else "DESACTIVATION"
    JournalAudit.enregistrer(request.user, action, f"Utilisateur {cible.username}")
    etat = "activé" if cible.is_active else "désactivé"
    messages.success(request, f"Le compte « {cible.username} » a été {etat}.")
    return redirect("utilisateur_liste")


@role_requis()
def utilisateur_reinitialiser_mdp(request, pk):
    cible = get_object_or_404(Utilisateur, pk=pk)
    _verifier_droits(request, cible)

    form = ReinitialisationMotDePasseForm(cible, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        JournalAudit.enregistrer(request.user, "REINITIALISATION_MDP", f"Utilisateur {cible.username}")
        messages.success(request, f"Le mot de passe de « {cible.username} » a été réinitialisé.")
        return redirect("utilisateur_liste")

    return render(request, "formulaire.html", {
        "form": form,
        "titre": f"Nouveau mot de passe pour « {cible.username} »",
        "aide": "Communiquez ce mot de passe à l'utilisateur en personne, puis demandez-lui de le changer dès sa prochaine connexion.",
        "url_retour": reverse("utilisateur_liste"),
    })


# ---------------------------------------------------------------- Mon compte

@login_required
def mot_de_passe_changer(request):
    form = ChangementMotDePasseForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = form.save()
        update_session_auth_hash(request, utilisateur)   # évite d'être déconnecté
        JournalAudit.enregistrer(request.user, "CHANGEMENT_MDP", f"Utilisateur {utilisateur.username}")
        messages.success(request, "Votre mot de passe a été modifié.")
        return redirect("tableau_de_bord")

    return render(request, "formulaire.html", {
        "form": form,
        "titre": "Changer mon mot de passe",
        "url_retour": reverse("tableau_de_bord"),
    })


# ---------------------------------------------------------------- Journal d'audit

@role_requis()
def journal_liste(request):
    entrees = JournalAudit.objects.select_related("utilisateur")

    q = request.GET.get("q", "").strip()
    if q:
        entrees = entrees.filter(
            Q(objet__icontains=q) | Q(details__icontains=q) | Q(utilisateur__username__icontains=q)
        )

    action = request.GET.get("action", "")
    if action:
        entrees = entrees.filter(action=action)

    date_debut = _lire_date(request.GET.get("du"))
    date_fin = _lire_date(request.GET.get("au"))
    if date_debut:
        entrees = entrees.filter(date__date__gte=date_debut)
    if date_fin:
        entrees = entrees.filter(date__date__lte=date_fin)

    actions = JournalAudit.objects.values_list("action", flat=True).distinct().order_by("action")
    page = Paginator(entrees, 25).get_page(request.GET.get("page"))

    return render(request, "utilisateurs/journal_liste.html", {
        "page": page,
        "q": q,
        "action": action,
        "actions": actions,
        "du": request.GET.get("du", ""),
        "au": request.GET.get("au", ""),
        "params": _params_sans_page(request),
    })