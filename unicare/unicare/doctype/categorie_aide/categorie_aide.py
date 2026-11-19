# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CategorieAide(Document):
	"""Une rubrique du centre d'aide du bureau. La lecture passe par `unicare.api.bureau_aide`."""

	def on_update(self):
		from unicare.aide.index import vider_cache

		vider_cache()

	def on_trash(self):
		from unicare.aide.index import vider_cache

		vider_cache()
