"""
Génération des documents PDF avec ReportLab (cahier des charges, module K).
Chaque document comporte : numéro, date, lignes, quantités, prix, total et informations de la pharmacie.
"""
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

VERT = colors.HexColor("#1f6b58")
STYLES = getSampleStyleSheet()
NORMAL = ParagraphStyle("normal_pg", parent=STYLES["Normal"], fontSize=9, leading=11)
PETIT = ParagraphStyle("petit_pg", parent=NORMAL, fontSize=7.5, leading=9, textColor=colors.HexColor("#555555"))
TITRE = ParagraphStyle("titre_pg", parent=STYLES["Heading1"], fontSize=15, textColor=VERT, spaceAfter=4)
DROITE = ParagraphStyle("droite_pg", parent=NORMAL, alignment=TA_RIGHT)


def ar(montant):
    """Montant en ariary avec séparateur de milliers : 85 000 Ar."""
    montant = Decimal(montant or 0).quantize(Decimal("1"))
    return f"{montant:,.0f} Ar".replace(",", " ")


def _entete_pharmacie():
    p = settings.PHARMACIE
    return [
        Paragraph(f"<b>{p['nom']}</b>", ParagraphStyle("n", parent=NORMAL, fontSize=11, textColor=VERT)),
        Paragraph(f"{p['adresse']} — Tél. {p['telephone']}", PETIT),
        Paragraph(f"{p['nif']} — {p['stat']}", PETIT),
        Spacer(1, 4 * mm),
    ]


def _tableau(donnees, largeurs, lignes_total=0):
    t = Table(donnees, colWidths=largeurs, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), VERT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1 - lignes_total), [colors.white, colors.HexColor("#f2f6f4")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if lignes_total:
        style += [
            ("FONTNAME", (0, -lignes_total), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE", (0, -lignes_total), (-1, -lignes_total), 1, VERT),
        ]
    t.setStyle(TableStyle(style))
    return t


def _pied(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(doc.leftMargin, 8 * mm, f"Édité le {timezone.localtime():%d/%m/%Y %H:%M} — PharmaGest")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _reponse_pdf(elements, nom_fichier, format_page=A4, marges=15 * mm):
    tampon = BytesIO()
    doc = SimpleDocTemplate(
        tampon, pagesize=format_page, leftMargin=marges, rightMargin=marges,
        topMargin=marges, bottomMargin=15 * mm, title=nom_fichier,
    )
    doc.build(elements, onFirstPage=_pied, onLaterPages=_pied)
    reponse = HttpResponse(tampon.getvalue(), content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="{nom_fichier}.pdf"'
    return reponse


# ---------------------------------------------------------------- Ventes

def recu_vente(vente):
    """Petit reçu de caisse (format A6)."""
    e = _entete_pharmacie()
    e += [
        Paragraph(f"<b>REÇU {vente.numero}</b>", ParagraphStyle("r", parent=NORMAL, fontSize=11)),
        Paragraph(f"{timezone.localtime(vente.date):%d/%m/%Y %H:%M} — Caissier : {vente.vendeur}", PETIT),
        Paragraph(f"Client : {vente.client or 'Client comptoir'}", PETIT),
        Spacer(1, 3 * mm),
    ]
    donnees = [["Article", "Qté", "P.U.", "Total"]]
    for l in vente.lignes.select_related("medicament", "lot"):
        donnees.append([
            Paragraph(f"{l.medicament}<br/><font size=6>Lot {l.lot.numero_lot} — exp. {l.lot.date_peremption:%m/%Y}</font>", PETIT),
            l.quantite, ar(l.prix_unitaire), ar(l.sous_total),
        ])
    donnees.append(["TOTAL", "", "", ar(vente.total)])
    e.append(_tableau(donnees, [38 * mm, 9 * mm, 18 * mm, 20 * mm], lignes_total=1))
    e.append(Spacer(1, 3 * mm))
    for p in vente.paiements.all():
        texte = f"{p.get_mode_display()} : {ar(p.montant)} — {p.get_statut_display()}"
        if p.montant_recu is not None:
            texte += f"<br/>Reçu : {ar(p.montant_recu)} — Rendu : {ar(p.monnaie_rendue)}"
        e.append(Paragraph(texte, PETIT))
    if vente.statut == vente.Statut.ANNULEE:
        e.append(Paragraph("<b>VENTE ANNULÉE</b>", ParagraphStyle("a", parent=NORMAL, textColor=colors.red)))
    e += [Spacer(1, 3 * mm), Paragraph("Merci de votre visite. Conservez ce reçu.", PETIT)]
    return _reponse_pdf(e, f"recu_{vente.numero}", format_page=A6, marges=7 * mm)


def facture_vente(vente):
    e = _entete_pharmacie()
    client = vente.client
    e += [
        Paragraph(f"FACTURE N° {vente.numero}", TITRE),
        Paragraph(f"Date : {timezone.localtime(vente.date):%d/%m/%Y}", NORMAL),
        Paragraph(
            f"Client : {client.nom if client else 'Client comptoir'}"
            + (f" — Tél. {client.telephone}" if client and client.telephone else "")
            + (f"<br/>{client.adresse}" if client and client.adresse else ""), NORMAL,
        ),
        Spacer(1, 5 * mm),
    ]
    donnees = [["Désignation", "Lot", "Quantité", "Prix unitaire", "Montant"]]
    for l in vente.lignes.select_related("medicament", "lot"):
        donnees.append([Paragraph(str(l.medicament), NORMAL), l.lot.numero_lot, l.quantite,
                        ar(l.prix_unitaire), ar(l.sous_total)])
    donnees.append(["Total", "", "", "", ar(vente.total)])
    e.append(_tableau(donnees, [70 * mm, 28 * mm, 20 * mm, 30 * mm, 32 * mm], lignes_total=1))
    e += [
        Spacer(1, 6 * mm),
        Paragraph("Mentions légales et fiscales à adapter à la réglementation applicable à Madagascar.", PETIT),
    ]
    return _reponse_pdf(e, f"facture_{vente.numero}")


def rapport_ventes(ventes, du, au, stats):
    e = _entete_pharmacie() + [
        Paragraph("Rapport des ventes", TITRE),
        Paragraph(f"Période du {du:%d/%m/%Y} au {au:%d/%m/%Y}", NORMAL),
        Spacer(1, 4 * mm),
        _tableau([
            ["Indicateur", "Valeur"],
            ["Nombre de ventes validées", stats["nb_ventes"]],
            ["Chiffre d'affaires (ventes validées − retours)", ar(stats["chiffre_affaires"])],
            ["Encaissements confirmés", ar(stats["encaissements"])],
            ["Marge commerciale brute (hors autres charges)", ar(stats["marge"])],
        ], [110 * mm, 60 * mm]),
        Spacer(1, 5 * mm),
    ]
    donnees = [["N°", "Date", "Client", "Vendeur", "Statut", "Total"]]
    for v in ventes:
        donnees.append([v.numero, f"{timezone.localtime(v.date):%d/%m/%Y %H:%M}", str(v.client or "Comptoir")[:28],
                        str(v.vendeur)[:20], v.get_statut_display(), ar(v.total)])
    e.append(_tableau(donnees, [27 * mm, 28 * mm, 45 * mm, 30 * mm, 18 * mm, 32 * mm]))
    return _reponse_pdf(e, f"rapport_ventes_{du:%Y%m%d}_{au:%Y%m%d}")


# ---------------------------------------------------------------- Achats

def bon_commande(commande):
    f = commande.fournisseur
    e = _entete_pharmacie() + [
        Paragraph(f"BON DE COMMANDE N° {commande.numero}", TITRE),
        Paragraph(f"Date : {timezone.localtime(commande.date_creation):%d/%m/%Y} — Statut : {commande.get_statut_display()}", NORMAL),
        Paragraph(f"Fournisseur : <b>{f.nom}</b> — Tél. {f.telephone}"
                  + (f" — {f.email}" if f.email else "") + (f"<br/>{f.adresse}" if f.adresse else ""), NORMAL),
        Spacer(1, 5 * mm),
    ]
    donnees = [["Médicament", "Quantité", "Prix unitaire", "Montant"]]
    for l in commande.lignes.select_related("medicament"):
        donnees.append([Paragraph(str(l.medicament), NORMAL), l.quantite_commandee, ar(l.prix_achat), ar(l.montant)])
    donnees.append(["Total", "", "", ar(commande.total)])
    e.append(_tableau(donnees, [90 * mm, 22 * mm, 34 * mm, 34 * mm], lignes_total=1))
    if commande.note:
        e += [Spacer(1, 4 * mm), Paragraph(f"Note : {commande.note}", NORMAL)]
    e += [Spacer(1, 15 * mm), Paragraph("Signature et cachet de la pharmacie :", NORMAL)]
    return _reponse_pdf(e, f"bon_commande_{commande.numero}")


def bon_reception(reception):
    commande = reception.commande
    e = _entete_pharmacie() + [
        Paragraph(f"BON DE RÉCEPTION N° {reception.numero}", TITRE),
        Paragraph(f"Date : {timezone.localtime(reception.date_reception):%d/%m/%Y %H:%M} — Reçu par : {reception.recu_par}", NORMAL),
        Paragraph(f"Commande : {commande.numero} — Fournisseur : <b>{commande.fournisseur}</b>", NORMAL),
        Spacer(1, 5 * mm),
    ]
    donnees = [["Médicament", "N° lot", "Péremption", "Quantité", "P.U.", "Montant"]]
    for l in reception.lignes.select_related("ligne_achat__medicament", "lot"):
        donnees.append([Paragraph(str(l.ligne_achat.medicament), NORMAL), l.lot.numero_lot,
                        f"{l.lot.date_peremption:%d/%m/%Y}", l.quantite, ar(l.prix_achat), ar(l.montant)])
    donnees.append(["Total", "", "", "", "", ar(reception.total)])
    e.append(_tableau(donnees, [62 * mm, 25 * mm, 23 * mm, 18 * mm, 25 * mm, 27 * mm], lignes_total=1))
    if reception.note:
        e += [Spacer(1, 4 * mm), Paragraph(f"Note : {reception.note}", NORMAL)]
    return _reponse_pdf(e, f"bon_reception_{reception.numero}")


def rapport_achats(receptions, du, au, total):
    e = _entete_pharmacie() + [
        Paragraph("Rapport des achats (réceptions)", TITRE),
        Paragraph(f"Période du {du:%d/%m/%Y} au {au:%d/%m/%Y} — Total réceptionné : <b>{ar(total)}</b>", NORMAL),
        Spacer(1, 5 * mm),
    ]
    donnees = [["Réception", "Date", "Commande", "Fournisseur", "Montant"]]
    for r in receptions:
        donnees.append([r.numero, f"{timezone.localtime(r.date_reception):%d/%m/%Y}", r.commande.numero,
                        str(r.commande.fournisseur)[:35], ar(r.total)])
    donnees.append(["Total", "", "", "", ar(total)])
    e.append(_tableau(donnees, [28 * mm, 24 * mm, 28 * mm, 66 * mm, 34 * mm], lignes_total=1))
    return _reponse_pdf(e, f"rapport_achats_{du:%Y%m%d}_{au:%Y%m%d}")


# ---------------------------------------------------------------- Stock

def rapport_stock(medicaments, valeur_totale):
    e = _entete_pharmacie() + [
        Paragraph("Rapport de stock", TITRE),
        Paragraph(f"État au {timezone.localtime():%d/%m/%Y %H:%M} — Valeur du stock vendable au prix d'achat : "
                  f"<b>{ar(valeur_totale)}</b>", NORMAL),
        Spacer(1, 5 * mm),
    ]
    donnees = [["Médicament", "Catégorie", "Stock total", "Vendable", "Seuil", "État"]]
    for m in medicaments:
        if m.stock_vendable_calc == 0:
            etat = "Rupture"
        elif m.stock_vendable_calc <= m.seuil_alerte:
            etat = "Stock faible"
        else:
            etat = "Normal"
        donnees.append([Paragraph(str(m), NORMAL), str(m.categorie)[:22], m.stock_total_calc,
                        m.stock_vendable_calc, m.seuil_alerte, etat])
    e.append(_tableau(donnees, [62 * mm, 36 * mm, 20 * mm, 20 * mm, 15 * mm, 27 * mm]))
    return _reponse_pdf(e, f"rapport_stock_{timezone.localdate():%Y%m%d}")


def rapport_peremptions(lots, jours):
    e = _entete_pharmacie() + [
        Paragraph("Produits périmés ou proches de la péremption", TITRE),
        Paragraph(f"Lots en stock périmés ou expirant dans les {jours} prochains jours — "
                  f"édité le {timezone.localdate():%d/%m/%Y}", NORMAL),
        Spacer(1, 5 * mm),
    ]
    donnees = [["Médicament", "N° lot", "Péremption", "Jours restants", "Quantité", "Statut"]]
    for lot in lots:
        donnees.append([Paragraph(str(lot.medicament), NORMAL), lot.numero_lot, f"{lot.date_peremption:%d/%m/%Y}",
                        lot.jours_restants, lot.quantite,
                        "PÉRIMÉ" if lot.est_perime else ("Bloqué" if lot.bloque else "À écouler")])
    e.append(_tableau(donnees, [62 * mm, 28 * mm, 24 * mm, 22 * mm, 18 * mm, 26 * mm]))
    return _reponse_pdf(e, f"peremptions_{timezone.localdate():%Y%m%d}")
