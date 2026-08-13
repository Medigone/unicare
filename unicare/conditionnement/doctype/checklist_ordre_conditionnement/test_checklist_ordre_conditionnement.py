# Copyright (c) 2026, IntraPro and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestChecklistOrdreConditionnement(FrappeTestCase):
	def test_requires_at_least_one_line(self):
		doc = frappe.get_doc(
			{
				"doctype": "Checklist Ordre Conditionnement",
				"titre": "CHK-TEST-EMPTY",
				"actif": 1,
			}
		)
		self.assertRaises(frappe.ValidationError, doc.validate)
