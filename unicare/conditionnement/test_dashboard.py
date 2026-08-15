# Copyright (c) 2026, IntraPro and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from unicare.conditionnement.dashboard import get_controles_non_conformes


class TestConditionnementDashboard(FrappeTestCase):
	def test_controles_non_conformes_returns_count(self):
		result = get_controles_non_conformes()
		self.assertIn("value", result)
		self.assertGreaterEqual(result["value"], 0)
		self.assertEqual(result["route"], ["List", "Ordre de Conditionnement"])
