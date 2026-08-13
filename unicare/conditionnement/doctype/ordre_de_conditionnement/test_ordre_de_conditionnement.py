# Copyright (c) 2026, IntraPro and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint

from unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement import (
	_item_lot_key,
)
from unicare.conditionnement.purchase_receipt_hooks import _ensure_native_batch
from unicare.conditionnement.stock import item_has_batch


def _first_value(doctype, field="name"):
	return frappe.db.get_value(doctype, {}, field)


def _make_item(item_type, item_name):
	item_group = _first_value("Item Group")
	stock_uom = _first_value("UOM")
	if not item_group or not stock_uom:
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_name": item_name,
			"item_group": item_group,
			"stock_uom": stock_uom,
			"is_stock_item": 1,
			"custom_type_conditionnement": item_type,
		}
	)
	doc.insert()
	return doc


class TestOrdreDeConditionnement(FrappeTestCase):
	def test_qty_rebut_is_sum_of_child_table(self):
		doc = frappe.new_doc("Ordre de Conditionnement")
		doc.append("rebuts", {"item_code": "A", "qty": 1.5})
		doc.append("rebuts", {"item_code": "B", "qty": 2.5})
		doc.calculate_qty_rebut()
		self.assertEqual(doc.qty_rebut, 4)

	def test_rebut_must_match_a_matiere(self):
		doc = frappe.new_doc("Ordre de Conditionnement")
		doc.warehouse_rebuts = "WH-REBUT"
		doc.append("matieres", {"item_code": "MP-1", "qty_theorique": 10, "qty_reelle": 8})
		doc.append("rebuts", {"item_code": "OTHER", "qty": 1})
		self.assertRaises(frappe.ValidationError, doc.validate_rebuts)

	def test_item_lot_key_ignores_batch_without_tracking(self):
		self.assertEqual(_item_lot_key("ITEM-NO-BATCH", "LOT-1"), ("ITEM-NO-BATCH", ""))

	def test_cloture_rejects_consumption_above_prepared(self):
		doc = frappe.new_doc("Ordre de Conditionnement")
		doc.append("matieres", {"item_code": "ITEM-NO-BATCH", "qty_theorique": 5, "qty_reelle": 4})
		doc.append("rebuts", {"item_code": "ITEM-NO-BATCH", "qty": 2})
		self.assertRaises(frappe.ValidationError, doc.validate_cloture_quantities)

	def test_apply_checklist_copies_modele_lignes(self):
		if not frappe.db.exists("DocType", "Checklist Ordre Conditionnement"):
			self.skipTest("DocType Checklist Ordre Conditionnement manquant")

		modele = frappe.get_doc(
			{
				"doctype": "Checklist Ordre Conditionnement",
				"titre": "CHK-TEST-COPY",
				"actif": 1,
				"lignes": [
					{"controle": "Contrôle A", "obligatoire": 1},
					{"controle": "Contrôle B", "obligatoire": 0},
				],
			}
		).insert()

		doc = frappe.new_doc("Ordre de Conditionnement")
		doc.modele_checklist = modele.name
		doc.apply_checklist()

		self.assertEqual(len(doc.checklist), 2)
		self.assertEqual(doc.checklist[0].controle, "Contrôle A")
		self.assertEqual(cint(doc.checklist[0].obligatoire), 1)
		self.assertEqual(doc.checklist[1].controle, "Contrôle B")
		self.assertEqual(cint(doc.checklist[1].obligatoire), 0)

	def test_apply_checklist_does_nothing_without_modele(self):
		doc = frappe.new_doc("Ordre de Conditionnement")
		doc.apply_checklist()
		self.assertFalse(doc.checklist)

	def test_apply_checklist_keeps_existing_rows(self):
		doc = frappe.new_doc("Ordre de Conditionnement")
		doc.modele_checklist = "INEXISTANT"
		doc.append("checklist", {"controle": "Déjà là", "obligatoire": 1})
		doc.apply_checklist()
		self.assertEqual(len(doc.checklist), 1)
		self.assertEqual(doc.checklist[0].controle, "Déjà là")


class TestPurchaseReceiptBatches(FrappeTestCase):
	def test_supplier_lot_creates_native_batch(self):
		item = _make_item("Fût", "Test fût lot fournisseur")
		if not item:
			self.skipTest("Item Group ou UOM manquant")

		self.assertTrue(item_has_batch(item.name))
		batch_id = f"FOUR-{item.name}"
		row = frappe._dict(item_code=item.name, batch_no=batch_id)
		_ensure_native_batch(row, None)
		self.assertTrue(frappe.db.exists("Batch", batch_id))
		self.assertEqual(frappe.db.get_value("Batch", batch_id, "item"), item.name)

	def test_existing_batch_for_other_item_is_rejected(self):
		item_a = _make_item("Fût", "Test fût A")
		item_b = _make_item("Fût", "Test fût B")
		if not item_a or not item_b:
			self.skipTest("Item Group ou UOM manquant")

		batch_id = f"FOUR-{item_a.name}"
		_ensure_native_batch(frappe._dict(item_code=item_a.name, batch_no=batch_id), None)
		row = frappe._dict(item_code=item_b.name, batch_no=batch_id)
		self.assertRaises(frappe.ValidationError, _ensure_native_batch, row, None)
