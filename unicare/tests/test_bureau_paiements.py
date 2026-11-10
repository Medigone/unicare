# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from unicare.api import bureau_bulk, bureau_factures, bureau_paiements
from unicare.tests import test_bureau_factures
from unicare.tests.test_bureau_commandes import _article
from unicare.tests.test_bureau_devis import _client


def _especes():
	return frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name")


class TestPaiements(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.client = _client()
		self.service = _article("Prestation essai paiement", 1000, stock=False)

	def tearDown(self):
		frappe.db.rollback()

	def _facture_validee(self, quantite=1):
		helper = test_bureau_factures.TestFactures()
		helper.client, helper.service = self.client, self.service
		_commande, facture = helper._facture(quantite=quantite)
		return bureau_factures.validate_facture(facture["name"], facture["modified"])

	def _values(self, **extra):
		return {
			"type": "encaissement_client",
			"tiers": self.client,
			"montant": 1000,
			"mode": _especes(),
			"date": today(),
			"affectations": [],
			**extra,
		}

	def test_pieces_ouvertes_echeance_d_abord(self):
		premiere = self._facture_validee()
		seconde = self._facture_validee(quantite=2)
		pieces = bureau_paiements.get_pieces_ouvertes("encaissement_client", self.client)
		self.assertEqual([piece["name"] for piece in pieces][:2], [premiere["name"], seconde["name"]])
		self.assertEqual([piece["reste"] for piece in pieces][:2], [1000, 2000])
		self.assertEqual(bureau_paiements.get_pieces_ouvertes("remboursement_client", self.client), [])

	def test_encaissement_reparti_avec_avance(self):
		premiere = self._facture_validee()
		seconde = self._facture_validee(quantite=2)
		name = bureau_paiements.create_paiement(
			json.dumps(
				self._values(
					montant=3500,
					affectations=[
						{"name": premiere["name"], "montant": 1000},
						{"name": seconde["name"], "montant": 2000},
					],
				)
			)
		)["name"]
		paiement = bureau_paiements.get_paiement(name)
		self.assertEqual((paiement["status"], paiement["type"]), ("Draft", "encaissement_client"))
		self.assertEqual((paiement["affecte"], paiement["non_affecte"]), (3000, 500))
		self.assertEqual(bureau_factures.get_facture(premiere["name"])["reste"], 1000)
		paiement = bureau_paiements.validate_paiement(name, paiement["modified"])
		self.assertEqual(paiement["status"], "Submitted")
		self.assertEqual(bureau_factures.get_facture(premiere["name"])["reste"], 0)
		self.assertEqual(bureau_factures.get_facture(seconde["name"])["status"], "Paid")
		response = bureau_paiements.get_paiements(view="non_affectes", page_length=500)
		self.assertIn(name, response["names"])
		paiement = bureau_paiements.cancel_paiement(name, paiement["modified"])
		self.assertEqual(paiement["status"], "Cancelled")
		self.assertEqual(bureau_factures.get_facture(premiere["name"])["reste"], 1000)

	def test_modification_du_brouillon(self):
		facture = self._facture_validee()
		name = bureau_paiements.create_paiement(json.dumps(self._values(montant=400)))["name"]
		paiement = bureau_paiements.get_paiement(name)
		self.assertEqual(paiement["non_affecte"], 400)
		pieces = bureau_paiements.get_pieces_ouvertes("encaissement_client", self.client, exclude=name)
		self.assertEqual(pieces[0]["deja"], 0)
		paiement = bureau_paiements.update_paiement(
			name,
			paiement["modified"],
			json.dumps(self._values(montant=400, affectations=[{"name": facture["name"], "montant": 400}])),
		)
		self.assertEqual((paiement["affecte"], paiement["affectations"][0]["name"]), (400, facture["name"]))
		bureau_paiements.delete_paiement(name, paiement["modified"])
		self.assertFalse(frappe.db.exists("Payment Entry", name))

	def test_remboursement_d_un_avoir(self):
		facture = self._facture_validee()
		facture = bureau_factures.encaisser(facture["name"], facture["modified"], 1000, _especes())["facture"]
		avoir = bureau_factures.create_avoir(facture["name"], facture["modified"])["name"]
		avoir = bureau_factures.get_facture(avoir)
		avoir = bureau_factures.validate_facture(avoir["name"], avoir["modified"])
		pieces = bureau_paiements.get_pieces_ouvertes("remboursement_client", self.client)
		self.assertEqual(
			[(piece["name"], piece["reste"], piece["avoir"]) for piece in pieces], [(avoir["name"], 1000, 1)]
		)
		name = bureau_paiements.create_paiement(
			json.dumps(
				self._values(
					type="remboursement_client", affectations=[{"name": avoir["name"], "montant": 1000}]
				)
			)
		)["name"]
		paiement = bureau_paiements.get_paiement(name)
		self.assertEqual((paiement["sens"], paiement["affecte"]), ("Pay", 1000))
		bureau_paiements.validate_paiement(name, paiement["modified"])
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", avoir["name"], "outstanding_amount")), 0)

	def test_refus_et_fournisseur(self):
		facture = self._facture_validee()
		for values in (
			{"montant": 0},
			{"tiers": ""},
			{"type": "inconnu"},
			{"mode": "Inventé"},
			{"montant": 500, "affectations": [{"name": facture["name"], "montant": 600}]},
			{"type": "remboursement_client", "affectations": [{"name": facture["name"], "montant": 100}]},
		):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				bureau_paiements.create_paiement(json.dumps(self._values(**values)))
		banque = frappe.db.get_value("Mode of Payment", {"type": "Bank", "enabled": 1}, "name")
		if banque:
			with self.assertRaises(frappe.ValidationError):
				bureau_paiements.create_paiement(json.dumps(self._values(mode=banque)))
		fournisseur = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		if fournisseur:
			name = bureau_paiements.create_paiement(
				json.dumps(self._values(type="paiement_fournisseur", tiers=fournisseur, montant=250))
			)["name"]
			paiement = bureau_paiements.get_paiement(name)
			self.assertEqual(
				(paiement["sens"], paiement["tiers_type"], paiement["non_affecte"]), ("Pay", "Supplier", 250)
			)
			self.assertIn(
				fournisseur,
				[row["name"] for row in bureau_paiements.search_tiers("paiement_fournisseur", fournisseur)],
			)
		self.assertIn("Payment Entry", bureau_bulk.BULK_DOCTYPES)
		options = bureau_paiements.get_paiement_options()
		self.assertTrue(
			{"encaissement_client", "remboursement_client"} <= {row["value"] for row in options["types"]}
		)
