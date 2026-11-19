# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import io

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.impression.production import contexte_production

MILLE = f"1{chr(0x202F)}000"


def _ordre(n_matieres=3, termine=False):
	"""Un ordre de conditionnement en mémoire (jamais enregistré)."""
	doc = frappe.new_doc("Ordre de Conditionnement")
	doc.name = "OC-TEST-IMPRESSION"
	doc.produit_fini, doc.nom_produit = "PF-TEST", "Bouteille Shampoing 250 ml"
	doc.qty_prevue, doc.uom, doc.date_prevue = 1000, "Unité", "2026-11-20"
	doc.workflow_state = "Terminé" if termine else "Planifié"
	doc.date_heure_planification = "2026-11-19 16:40:00"
	if termine:
		doc.qty_reelle_pf, doc.qty_rebut, doc.rendement_reel = 985, 15, 98.5
		doc.date_heure_cloture, doc.duree_totale = "2026-11-20 12:10:00", 1170
	for i in range(1, n_matieres + 1):
		doc.append(
			"matieres",
			{
				"item_code": f"MAT-{i:03d}",
				"item_name": f"M{i}Q Matière de conditionnement",
				"type_ingredient": "Fût" if i == 1 else "Conditionnement",
				"qty_theorique": 1000,
				"qty_reelle": 1012 if termine else 0,
				"uom": "Unité",
			},
		)
	doc.append("checklist", {"controle": "Lots vérifiés", "obligatoire": 1, "conforme": 1})
	doc.append("checklist", {"controle": "Ligne dégagée", "obligatoire": 1, "conforme": 0})
	return doc


def _texte_pdf(doc, format_impression):
	from frappe.utils.pdf import get_pdf
	from pypdf import PdfReader

	html = frappe.get_print(doc.doctype, doc.name, doc=doc, print_format=format_impression)
	pdf = PdfReader(io.BytesIO(get_pdf(html)))
	return len(pdf.pages), " ".join(" ".join(p.extract_text().split()) for p in pdf.pages)


class TestDocumentsProduction(FrappeTestCase):
	def test_fiche_a_remplir(self):
		ctx = contexte_production(_ordre(), "fiche")
		self.assertEqual(ctx["titre"], "FICHE D'ORDRE DE PRODUCTION")
		self.assertIn("DOCUMENT INTERNE", ctx["maison"])
		ligne = ctx["pages"][0]["lignes"][0]["cellules"]
		self.assertIsNone(ligne["reel"])  # à remplir à la main tant que l'ordre n'est pas terminé
		self.assertEqual(ligne["theorique"], MILLE)
		resultat = next(s for s in ctx["apres"] if s["type"] == "saisies")
		self.assertTrue(all(valeur is None for _l, valeur, _u in resultat["champs"]))

	def test_checklist(self):
		ctx = contexte_production(_ordre(), "checklist")
		cellules = [ligne["cellules"] for ligne in ctx["pages"][0]["lignes"]]
		self.assertEqual([c["conforme"]["coche"] for c in cellules], ["Oui", None])
		self.assertEqual([c["obligatoire"] for c in cellules], [1, 1])
		self.assertIn("decision", [s["type"] for s in ctx["apres"]])

	def test_compte_rendu(self):
		ctx = contexte_production(_ordre(termine=True), "compte_rendu")
		chiffres = ctx["avant"][0]["chiffres"]
		self.assertEqual([c[1] for c in chiffres], [MILLE, "985", "15", "98,5 %"])
		self.assertEqual(ctx["pages"][0]["lignes"][0]["cellules"]["ecart"], "+ 12")
		deroulement = ctx["avant"][1]["tableaux"][0]["lignes"]
		self.assertEqual(deroulement[-1]["Durée"], "19 h 30")

	def test_fiche_longue_sans_ligne_rognee(self):
		doc = _ordre(n_matieres=45)
		attendues = len(contexte_production(doc, "fiche")["pages"])
		pages, texte = _texte_pdf(doc, "Unicare Fiche d'ordre")
		self.assertGreater(attendues, 1)
		self.assertEqual(pages, attendues)
		self.assertEqual([i for i in range(1, 46) if f"M{i}Q" not in texte], [])
		self.assertIn(f"Page {attendues}/{attendues}", texte)
		self.assertIn("CHEF D'ATELIER", texte)

	def test_bon_de_transfert(self):
		depots = frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name", limit=2)
		doc = frappe.new_doc("Stock Entry")
		doc.name, doc.purpose, doc.stock_entry_type = (
			"MAT-STE-TEST-IMPRESSION",
			"Material Transfer",
			"Material Transfer",
		)
		doc.company = frappe.get_all("Company", pluck="name", limit=1)[0]
		doc.posting_date, doc.posting_time = "2026-11-20", "07:45:00"
		for i in range(3):
			doc.append(
				"items",
				{
					"item_code": f"ART-{i}",
					"item_name": f"T{i}Q Article",
					"qty": 10 * (i + 1),
					"uom": "Unité",
					"s_warehouse": depots[0],
					"t_warehouse": depots[-1],
				},
			)
		ctx = contexte_production(doc)
		self.assertEqual(ctx["titre"], "BON DE TRANSFERT DE MATIÈRES")
		self.assertIn(("Type", "Transfert"), ctx["droite"])
		self.assertEqual(ctx["colonnes"][-1]["cle"], "recu")
		_pages, texte = _texte_pdf(doc, "Unicare Bon de mouvement")
		self.assertIn("T2Q", texte)
		self.assertIn("REMIS PAR", texte)


class TestImpressionGroupee(FrappeTestCase):
	def test_un_pdf_pour_plusieurs_pieces(self):
		import json

		from pypdf import PdfReader

		from unicare.api import bureau_impression

		noms = frappe.get_all("Stock Entry", filters={"docstatus": 1}, pluck="name", limit=2)
		if len(noms) < 2:
			self.skipTest("il faut deux mouvements validés")
		seuls = []
		for nom in noms:
			bureau_impression.imprimer("Stock Entry", json.dumps([nom]))
			seuls.append(len(PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages))
		bureau_impression.imprimer("Stock Entry", json.dumps(noms))
		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filename.startswith("Bons-de-mouvement-"))
		self.assertEqual(len(PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages), sum(seuls))

	def test_refus(self):
		from unicare.api import bureau_impression

		with self.assertRaises(frappe.ValidationError):
			bureau_impression.imprimer("Customer", '["x"]')
		with self.assertRaises(frappe.ValidationError):
			bureau_impression.imprimer("Sales Invoice", "[]")
		with self.assertRaises(frappe.ValidationError):
			bureau_impression.imprimer("Sales Invoice", str([f"F{i}" for i in range(101)]).replace("'", '"'))
