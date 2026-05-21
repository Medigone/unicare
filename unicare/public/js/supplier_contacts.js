function sync_supplier_disabled_from_statut(frm) {
	if (!frm.fields_dict.custom_statut) {
		return;
	}

	frm.set_value("disabled", frm.doc.custom_statut === "Exclu" ? 1 : 0);
}

function setup_supplier_name_uppercase(frm) {
	const field = frm.fields_dict.supplier_name;
	if (!field?.$input || field.$input.data("uppercase-bound")) {
		return;
	}

	field.$input.data("uppercase-bound", true);
	field.$input.on("input", function () {
		const value = $(this).val();
		const upper = value.toUpperCase();
		if (value !== upper) {
			$(this).val(upper);
			frm.doc.supplier_name = upper;
		}
	});
}

frappe.ui.form.on("Supplier", {
	setup(frm) {
		if (frm.doc.__islocal && !frm.doc.custom_statut) {
			frm.set_value("custom_statut", "Actif");
		}
	},

	custom_statut(frm) {
		sync_supplier_disabled_from_statut(frm);
	},

	supplier_name(frm) {
		if (frm.doc.supplier_name && frm.doc.supplier_name !== frm.doc.supplier_name.toUpperCase()) {
			frm.set_value("supplier_name", frm.doc.supplier_name.toUpperCase());
		}
	},

	refresh(frm) {
		setup_supplier_name_uppercase(frm);

		if (frm.fields_dict.disabled) {
			frm.set_df_property("disabled", "hidden", 1);
		}

		if (frm.doc.__islocal && !frm.doc.custom_statut) {
			frm.set_value("custom_statut", "Actif");
		}

		sync_supplier_disabled_from_statut(frm);
		if (!frm.fields_dict.custom_contact_html_custom) {
			return;
		}

		const html_content = `
			<div id="title" style="margin-top: 5px; font-size: 14px;">Liste Contacts</div>
			<div id="contacts-table" style="margin-top: 10px;"></div>
			<button class="btn btn-secondary btn-xs" id="add-contact-btn" style="margin-top: 10px; margin-bottom: 10px;">Ajouter Contact</button>
		`;
		frm.get_field("custom_contact_html_custom").$wrapper.html(html_content);

		function load_contacts() {
			frappe.call({
				method: "unicare.supplier_hooks.get_supplier_contacts",
				args: { supplier: frm.doc.name },
				callback(r) {
					if (!r.message) {
						return;
					}

					let table_html = `<table id="contacts-table-inner">
						<thead>
							<tr>
								<th>Contact</th>
								<th>Fonction</th>
								<th>Mobile</th>
								<th>Email</th>
							</tr>
						</thead>
						<tbody>`;

					r.message.forEach((contact) => {
						table_html += `<tr class="contact-row" data-docname="${contact.docname}">
							<td><strong>${contact.contact || "-"}</strong></td>
							<td>${contact.designation || "-"}</td>
							<td>${contact.mobile || "-"}</td>
							<td>${contact.email || "-"}</td>
						</tr>`;
					});

					table_html += "</tbody></table>";
					frm.get_field("custom_contact_html_custom").$wrapper.find("#contacts-table").html(table_html);

					const css = `
						<style>
						#contacts-table { overflow-x: auto; }
						#contacts-table-inner {
							border-collapse: separate;
							border-spacing: 0;
							width: 100%;
							border: 0.4px solid #e9ecef;
							border-radius: 8px;
							overflow: hidden;
							font-size: 12px;
						}
						#contacts-table-inner th {
							background-color: #f2f2f2;
							border: 0.4px solid #e9ecef;
							padding: 8px;
							white-space: nowrap;
						}
						#contacts-table-inner td {
							border: 0.4px solid #e9ecef;
							padding: 8px;
							white-space: nowrap;
						}
						#contacts-table-inner thead tr:first-child th:first-child { border-top-left-radius: 8px; }
						#contacts-table-inner thead tr:first-child th:last-child { border-top-right-radius: 8px; }
						#contacts-table-inner tbody tr:last-child td:first-child { border-bottom-left-radius: 8px; }
						#contacts-table-inner tbody tr:last-child td:last-child { border-bottom-right-radius: 8px; }
						#contacts-table-inner tbody tr.contact-row { cursor: pointer; }
						</style>
					`;

					const $wrapper = frm.get_field("custom_contact_html_custom").$wrapper;
					if ($wrapper.find("style").length === 0) {
						$wrapper.append(css);
					}

					$wrapper.find("#contacts-table-inner tbody").off("click", "tr.contact-row").on("click", "tr.contact-row", function () {
						frappe.set_route("Form", "Contact", $(this).attr("data-docname"));
					});
				},
			});
		}

		if (frm.doc.name) {
			load_contacts();
		}

		frm.get_field("custom_contact_html_custom").$wrapper.find("#add-contact-btn").off("click").on("click", () => {
			frappe.prompt(
				[
					{ fieldname: "first_name", fieldtype: "Data", label: __("First Name"), reqd: 1 },
					{ fieldname: "last_name", fieldtype: "Data", label: __("Last Name"), reqd: 0 },
					{ fieldname: "designation", fieldtype: "Data", label: __("Fonction"), reqd: 0 },
					{ fieldname: "mobile_no", fieldtype: "Data", label: __("Téléphone Mobile"), reqd: 1 },
					{ fieldname: "email", fieldtype: "Data", label: __("Email"), reqd: 0 },
					{ fieldname: "is_primary", fieldtype: "Check", label: __("Est Contact Principal"), default: 0 },
				],
				(values) => {
					const contact_doc = {
						doctype: "Contact",
						first_name: values.first_name,
						last_name: values.last_name,
						designation: values.designation,
						is_primary_contact: 1,
						links: [{ link_doctype: "Supplier", link_name: frm.doc.name }],
						phone_nos: [{ phone: values.mobile_no, is_primary_mobile_no: 1 }],
					};

					if (values.email) {
						contact_doc.email_ids = [{ email_id: values.email, is_primary: 1 }];
					}

					frappe.call({
						method: "frappe.client.insert",
						args: { doc: contact_doc },
						callback(r) {
							if (!r.message) {
								return;
							}

							frappe.msgprint(__("Contact ajouté avec succès"));

							if (values.is_primary) {
								frappe.call({
									method: "frappe.client.set_value",
									args: {
										doctype: "Supplier",
										name: frm.doc.name,
										fieldname: "supplier_primary_contact",
										value: r.message.name,
									},
									callback() {
										frappe.msgprint(__("Fournisseur mis à jour avec le contact principal"));
									},
								});
							}

							load_contacts();
						},
					});
				},
				__("Ajouter un Contact"),
				__("Créer")
			);
		});
	},
});
