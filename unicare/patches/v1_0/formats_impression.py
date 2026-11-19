# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Les formats d'impression Unicare deviennent ceux par défaut de leurs pièces (bureau et /app)."""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter

FORMATS = {
	"Sales Invoice": "Unicare Facture",
	"Quotation": "Unicare Devis",
	"Sales Order": "Unicare Commande",
	"Delivery Note": "Unicare Bon de livraison",
	"Payment Entry": "Unicare Reçu de paiement",
	"Purchase Order": "Unicare Bon de commande",
	"Ordre de Conditionnement": "Unicare Fiche d'ordre",
	"Stock Entry": "Unicare Bon de mouvement",
}


def execute():
	for doctype, format_impression in FORMATS.items():
		make_property_setter(
			doctype,
			None,
			"default_print_format",
			format_impression,
			"Data",
			for_doctype=True,
			validate_fields_for_doctype=False,
		)
