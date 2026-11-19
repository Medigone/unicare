# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import today


class ArticleAide(Document):
	"""Un article du centre d'aide : le Markdown saisi est rendu en HTML assaini à chaque enregistrement."""

	def validate(self):
		from unicare.aide.rendu import nettoyer_ecrans, rendre

		self.ecrans = nettoyer_ecrans(self.ecrans)
		self.contenu_html, self.duree_lecture = rendre(self.contenu_markdown or "")
		if self.has_value_changed("contenu_markdown") or not self.date_revision:
			self.date_revision = today()

	def on_update(self):
		from unicare.aide.index import vider_cache

		vider_cache()

	def on_trash(self):
		from unicare.aide.index import vider_cache

		vider_cache()
