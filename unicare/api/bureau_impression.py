# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Impression groupée depuis les listes du bureau : les pièces cochées, dans un seul PDF, chacune avec ses pages.

GET /api/method/unicare.api.bureau_impression.imprimer?doctype=…&noms=["…","…"][&document=…] : le PDF s'affiche
dans l'onglet (Content-Disposition inline), prêt à imprimer.
"""

import io
import json

import frappe
from frappe import _
from frappe.utils import nowdate
from pypdf import PdfWriter

from unicare.api.bureau_postes import require_bureau

MAX_PIECES = 100

# Les pièces qu'on imprime par lot, et le nom du fichier.
IMPRIMABLES = {
	"Sales Invoice": "Factures",
	"Quotation": "Devis",
	"Sales Order": "Commandes",
	"Delivery Note": "Bons-de-livraison",
	"Payment Entry": "Recus-de-paiement",
	"Purchase Order": "Bons-de-commande",
	"Stock Entry": "Bons-de-mouvement",
	"Ordre de Conditionnement": "Ordres",
}
# Un ordre a plusieurs documents ; les autres pièces prennent leur format par défaut (formats Unicare).
DOCUMENTS_ORDRE = {
	"fiche": ("Unicare Fiche d'ordre", "Fiches-d-ordre"),
	"checklist": ("Unicare Checklist avant production", "Checklists"),
	"compte_rendu": ("Unicare Compte rendu de production", "Comptes-rendus"),
}


def _noms(noms):
	if isinstance(noms, str):
		noms = json.loads(noms)
	noms = [str(n) for n in noms or [] if n]
	return list(dict.fromkeys(noms))


@frappe.whitelist(methods=["GET"])
def imprimer(doctype, noms, document=None):
	require_bureau()
	if doctype not in IMPRIMABLES:
		frappe.throw(_("Ces pièces ne s'impriment pas depuis la liste."))
	noms = _noms(noms)
	if not noms:
		frappe.throw(_("Cochez au moins une pièce à imprimer."))
	if len(noms) > MAX_PIECES:
		frappe.throw(
			_("{0} pièces au plus par impression : vous en avez coché {1}.").format(MAX_PIECES, len(noms))
		)

	format_impression, fichier = None, IMPRIMABLES[doctype]
	if doctype == "Ordre de Conditionnement":
		format_impression, fichier = DOCUMENTS_ORDRE.get(document or "fiche", DOCUMENTS_ORDRE["fiche"])

	from frappe.www.printview import validate_print_permission

	writer = PdfWriter()
	for nom in noms:
		doc = frappe.get_doc(doctype, nom)
		validate_print_permission(doc)  # une pièce interdite arrête tout, plutôt que de manquer en silence
		writer = frappe.get_print(
			doctype, nom, format_impression, doc=doc, as_pdf=True, output=writer, no_letterhead=1
		)

	flux = io.BytesIO()
	writer.write(flux)
	frappe.local.response.filename = f"{fichier}-{nowdate()}.pdf"
	frappe.local.response.filecontent = flux.getvalue()
	frappe.local.response.type = "pdf"
