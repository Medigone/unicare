# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import io
from itertools import pairwise

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.impression import pagination as P
from unicare.impression.contexte import contexte_impression
from unicare.impression.montants import en_lettres, montant, quantite, taux

FINE, INSECABLE, MOINS = chr(0x202F), chr(0xA0), chr(0x2212)


def _facture(n, avoir=False):
	"""Une facture en mémoire (jamais enregistrée) de n lignes, aux désignations repérables « Z<i>Q »."""
	item = frappe.get_all("Item", filters={"is_sales_item": 1, "disabled": 0}, pluck="name", limit=1)[0]
	doc = frappe.new_doc("Sales Invoice")
	doc.customer = frappe.get_all("Customer", pluck="name", limit=1)[0]
	doc.company = frappe.get_all("Company", pluck="name", limit=1)[0]
	doc.posting_date, doc.set_posting_time, doc.due_date = "2026-11-19", 1, "2026-12-19"
	for i in range(n):
		doc.append("items", {"item_code": item, "qty": 100 + 10 * i, "rate": 100 + i})
	doc.set_missing_values()
	for i, ligne in enumerate(doc.items, 1):
		ligne.item_name = f"Z{i}Q Lotion hydratante corps, flacon 250 ml"
	if avoir:
		doc.is_return, doc.return_against = 1, "ACC-SINV-2026-00001"
	doc.calculate_taxes_and_totals()
	doc.name = "ACC-SINV-TEST-IMPRESSION"
	return doc


class TestMontants(FrappeTestCase):
	def test_chiffres(self):
		self.assertEqual(montant(756840), f"756{FINE}840,00")
		self.assertEqual(montant(-19040), f"{MOINS}{INSECABLE}19{FINE}040,00")
		self.assertEqual(montant(1000000, 0), f"1{FINE}000{FINE}000")
		self.assertEqual(quantite(2.5), "2,5")
		self.assertEqual(quantite(1200), f"1{FINE}200")
		self.assertEqual(taux(19), f"19{INSECABLE}%")

	def test_en_lettres(self):
		self.assertEqual(
			en_lettres(756840),
			"sept cent cinquante-six mille huit cent quarante dinars algériens et zéro centime",
		)
		self.assertEqual(en_lettres(1000000), "un million de dinars algériens et zéro centime")
		self.assertEqual(en_lettres(1.5), "un dinar algérien et cinquante centimes")
		self.assertEqual(en_lettres(-19040.01), "dix-neuf mille quarante dinars algériens et un centime")


class TestPagination(FrappeTestCase):
	def _lignes(self, n, hauteur=P.LIGNE):
		return [
			{"idx": i, "hauteur": hauteur, "sommes": {"qte": 10, "montant": 100.0}} for i in range(1, n + 1)
		]

	def test_une_page(self):
		pages = P.paginer(self._lignes(5), hauteur_fin=100)
		self.assertEqual(len(pages), 1)
		self.assertIsNone(pages[0]["report_sortie"])
		self.assertIsNone(pages[0]["cumul_final"])

	def test_reports(self):
		pages = P.paginer(self._lignes(70), hauteur_fin=100)
		self.assertGreater(len(pages), 2)
		for avant, apres in pairwise(pages):
			self.assertEqual(
				apres["report_entree"], avant["report_sortie"]
			)  # le report reprend le total à reporter
			self.assertEqual(apres["ligne_avant"], avant["derniere_ligne"])
		self.assertEqual(pages[-1]["cumul_final"], {"qte": 700, "montant": 7000.0})
		self.assertEqual([p["numero"] for p in pages], list(range(1, len(pages) + 1)))
		self.assertTrue(all(p["total"] == len(pages) for p in pages))

	def test_la_fin_ne_reste_pas_seule(self):
		# assez de lignes pour remplir la première page : la fin n'y tient plus, la dernière ligne la suit
		premiere = P.PAGE - P.PIED - P.ENTETE - P.LIGNE_TITRE - P.LIGNE_REPORT
		n = int(premiere // P.LIGNE)
		pages = P.paginer(self._lignes(n), hauteur_fin=120)
		self.assertEqual(len(pages), 2)
		self.assertEqual([ligne["idx"] for ligne in pages[1]["lignes"]], [n])

	def test_hauteur_des_designations_longues(self):
		self.assertEqual(P.hauteur_ligne("court"), P.LIGNE)
		self.assertAlmostEqual(P.hauteur_ligne("x" * 100), P.LIGNE + 2 * P.LIGNE_EN_PLUS)


class TestContexte(FrappeTestCase):
	def test_facture_longue(self):
		doc = _facture(40)
		ctx = contexte_impression(doc)
		self.assertEqual(ctx["titre"], "FACTURE")
		self.assertGreater(len(ctx["pages"]), 1)
		self.assertIn(("Statut", "Brouillon, sans valeur"), ctx["meta"])
		net = doc.rounded_total or doc.grand_total
		self.assertIn(en_lettres(net), ctx["lettres"])
		self.assertEqual(ctx["total"][1], f"{montant(net)} DA")
		self.assertEqual(ctx["pages"][-1]["cumul_final"]["montant"], montant(doc.net_total))
		self.assertEqual([cle for cle, _v in ctx["tiers"]["ids"]], ["RC", "NIF", "NIS", "AI"])

	def test_avoir(self):
		ctx = contexte_impression(_facture(2, avoir=True))
		self.assertEqual(ctx["titre"], "FACTURE D'AVOIR")
		self.assertIn("ACC-SINV-2026-00001", dict(ctx["meta"])["Facture d'origine"])
		self.assertIn("en faveur du client", ctx["lettres"])
		self.assertIsNone(ctx.get("a_gauche"))

	def test_pdf_sans_ligne_rognee(self):
		"""Le vrai PDF : autant de pages que prévu, chaque ligne et chaque pied de page présents."""
		from frappe.utils.pdf import get_pdf
		from pypdf import PdfReader

		doc = _facture(30)
		attendues = len(contexte_impression(doc)["pages"])
		html = frappe.get_print(doc.doctype, doc.name, doc=doc, print_format="Unicare Facture")
		pdf = PdfReader(io.BytesIO(get_pdf(html)))
		texte = " ".join(" ".join(page.extract_text().split()) for page in pdf.pages)
		self.assertEqual(len(pdf.pages), attendues)
		self.assertEqual([i for i in range(1, 31) if f"Z{i}Q" not in texte], [])
		for numero in range(1, attendues + 1):
			self.assertIn(f"Page {numero}/{attendues}", texte)
		self.assertIn("Report de la page 1", texte)
		self.assertIn("Net à payer TTC", texte)

	def test_bon_de_livraison_valorise(self):
		"""En Algérie le bon de livraison porte les prix, la TVA et les totaux, comme une facture."""
		from frappe.utils.pdf import get_pdf
		from pypdf import PdfReader

		item = frappe.get_all("Item", filters={"is_sales_item": 1, "disabled": 0}, pluck="name", limit=1)[0]
		doc = frappe.new_doc("Delivery Note")
		doc.customer = frappe.get_all("Customer", pluck="name", limit=1)[0]
		doc.company = frappe.get_all("Company", pluck="name", limit=1)[0]
		doc.posting_date, doc.set_posting_time = "2026-11-17", 1
		for i in range(3):
			doc.append("items", {"item_code": item, "qty": 100 * (i + 1), "rate": 320})
		doc.set_missing_values()
		doc.calculate_taxes_and_totals()
		doc.name = "MAT-DN-TEST-IMPRESSION"
		ctx = contexte_impression(doc)
		self.assertEqual(ctx["titre"], "BON DE LIVRAISON")
		self.assertEqual([c["cle"] for c in ctx["colonnes"]][-3:], ["pu", "tva", "montant"])
		self.assertEqual(ctx["total"], ("Total TTC", f"{montant(doc.grand_total)} DA"))
		self.assertIn("présent bon de livraison", ctx["lettres"])
		self.assertIn("reserves", [b["type"] for b in ctx["encadres"]])
		html = frappe.get_print(doc.doctype, doc.name, doc=doc, print_format="Unicare Bon de livraison")
		texte = " ".join(
			" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(get_pdf(html))).pages
		)
		self.assertIn("Total TTC", texte)
		self.assertIn("P.U. HT", texte)
