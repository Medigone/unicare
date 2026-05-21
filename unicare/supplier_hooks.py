import frappe
from erpnext.buying.doctype.supplier.supplier import Supplier


class CustomSupplier(Supplier):
	def autoname(self):
		from frappe.model.naming import make_autoname

		self.name = make_autoname("FR-.#####")

	def validate(self):
		if not self.custom_statut:
			self.custom_statut = "Exclu" if self.disabled else "Actif"

		self.disabled = 1 if self.custom_statut == "Exclu" else 0

		if (
			frappe.defaults.get_global_default("supp_master_name") == "Naming Series"
			and not self.naming_series
		):
			self.naming_series = "FR-.#####"

		super().validate()

		if self.supplier_name:
			self.supplier_name = self.supplier_name.upper()


@frappe.whitelist()
def get_supplier_contacts(supplier):
	contacts_data = frappe.db.sql(
		"""
		SELECT
			c.name AS docname,
			TRIM(CONCAT_WS(' ', c.first_name, c.last_name)) AS contact,
			c.designation,
			MAX(CASE WHEN pn.is_primary_mobile_no = 1 THEN pn.phone END) AS mobile,
			MAX(CASE WHEN e.is_primary = 1 THEN e.email_id END) AS email
		FROM `tabContact` c
		LEFT JOIN `tabDynamic Link` dl
			ON c.name = dl.parent AND dl.link_doctype = 'Supplier' AND dl.link_name = %s
		LEFT JOIN `tabContact Phone` pn ON c.name = pn.parent
		LEFT JOIN `tabContact Email` e ON c.name = e.parent
		WHERE dl.link_name IS NOT NULL
		GROUP BY c.name
		""",
		(supplier,),
		as_dict=True,
	)

	return contacts_data
