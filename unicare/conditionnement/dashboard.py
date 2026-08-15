# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

from unicare.conditionnement.constants import STATUT_EN_PRODUCTION, STATUT_PREPARE

PARENT_ORDRE = "Ordre de Conditionnement"


@frappe.whitelist()
def get_controles_non_conformes(filters=None):
	count = frappe.db.sql(
		"""
		select count(*)
		from `tabChecklist Preparation` cp
		inner join `tabOrdre de Conditionnement` o on o.name = cp.parent
		where cp.parenttype = %s
			and cp.obligatoire = 1
			and ifnull(cp.conforme, 0) = 0
			and o.workflow_state in (%s, %s)
		""",
		(PARENT_ORDRE, STATUT_PREPARE, STATUT_EN_PRODUCTION),
	)[0][0]

	return {
		"value": cint(count),
		"fieldtype": "Int",
		"route": ["List", PARENT_ORDRE],
		"route_options": {
			"workflow_state": ["in", [STATUT_PREPARE, STATUT_EN_PRODUCTION]],
		},
	}
