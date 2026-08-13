// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

const WIZARD_STEPS = [
	{ key: "planifier", label: __("Planifier") },
	{ key: "preparer", label: __("Préparer") },
	{ key: "produire", label: __("Produire") },
	{ key: "cloturer", label: __("Clôturer") },
];

frappe.ui.form.on("Ordre de Conditionnement", {
	onload(frm) {
		hide_native_workflow_buttons(frm);
		if (frm.is_new()) {
			frappe.db.get_doc("Parametres Conditionnement").then((p) => {
				if (!frm.doc.warehouse_mp && p.warehouse_mp) {
					frm.set_value("warehouse_mp", p.warehouse_mp);
				}
				if (!frm.doc.warehouse_conditionnement && p.warehouse_conditionnement) {
					frm.set_value("warehouse_conditionnement", p.warehouse_conditionnement);
				}
				if (!frm.doc.warehouse_atelier && p.warehouse_atelier) {
					frm.set_value("warehouse_atelier", p.warehouse_atelier);
				}
				if (!frm.doc.warehouse_pf && p.warehouse_pf) {
					frm.set_value("warehouse_pf", p.warehouse_pf);
				}
				if (!frm.doc.warehouse_rebuts && p.warehouse_rebuts) {
					frm.set_value("warehouse_rebuts", p.warehouse_rebuts);
				}
			});
		}
	},
	refresh(frm) {
		frm._ow_expect_clean = !frm.doc.__unsaved && !frm.is_new();
		frm._ow_sync = true;
		const planning_locked = (frm.doc.workflow_state || "Brouillon") !== "Brouillon";
		["date_prevue", "recette", "qty_prevue"].forEach((fieldname) => {
			frm.set_df_property(fieldname, "read_only", planning_locked);
		});
		frm.set_query("recette", () => ({
			filters: {
				actif: 1,
				...(frm.doc.produit_fini ? { produit_fini: frm.doc.produit_fini } : {}),
			},
		}));
		frm.set_query("modele_checklist", () => ({
			filters: {
				actif: 1,
			},
		}));
		frm.set_query("lot_pf", () => ({
			filters: {
				item: frm.doc.produit_fini || "",
				disabled: 0,
			},
		}));
		frm.set_query("batch_no", "matieres", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: row.item_code,
					warehouse: warehouse_for_stock(frm, row),
				},
			};
		});
		frm.set_query("batch_no", "rebuts", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: row.item_code,
					warehouse: frm.doc.warehouse_atelier || "",
				},
			};
		});
		frm.set_query("item_code", "rebuts", () => {
			const items = (frm.doc.matieres || []).map((row) => row.item_code).filter(Boolean);
			if (!items.length) {
				return { filters: { name: ["in", [""]] } };
			}
			return { filters: { name: ["in", items] } };
		});

		relax_lot_mandatory();
		setup_wizard(frm);
		refresh_all_stocks(frm);
		if (frm._ow_expect_clean) {
			frm.doc.__unsaved = 0;
		}
	},
	recette(frm) {
		if (frm._ow_sync) {
			return;
		}
		charger_recette(frm);
	},
	modele_checklist(frm) {
		if (frm._ow_sync) {
			return;
		}
		charger_checklist(frm);
	},
	qty_prevue(frm) {
		if (frm._ow_sync) {
			return;
		}
		charger_recette(frm);
	},
	generer_lot_pf(frm) {
		if (!frm.doc.produit_fini) {
			frappe.msgprint(__("Sélectionnez d'abord une recette / un produit fini."));
			return;
		}

		const create_lot = () => {
			frappe.call({
				method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.generer_lot_pf",
				args: {
					produit_fini: frm.doc.produit_fini,
					ordre: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Création du lot…"),
				callback(r) {
					if (!r.message) {
						return;
					}
					frm.set_value("lot_pf", r.message);
					frappe.show_alert({
						message: __("Lot {0} créé", [r.message]),
						indicator: "green",
					});
				},
			});
		};

		if (frm.doc.lot_pf) {
			frappe.confirm(
				__("Un lot est déjà renseigné ({0}). Générer un nouveau lot ?", [frm.doc.lot_pf]),
				create_lot
			);
		} else {
			create_lot();
		}
	},
});

frappe.ui.form.on("Matiere Ordre Conditionnement", {
	batch_no(frm, cdt, cdn) {
		refresh_stock(frm, cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		refresh_stock(frm, cdt, cdn);
	},
	item_code(frm, cdt, cdn) {
		refresh_stock(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Rebut Ordre Conditionnement", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}
		const matiere = (frm.doc.matieres || []).find((line) => line.item_code === row.item_code);
		if (matiere) {
			if (!row.uom && matiere.uom) {
				frappe.model.set_value(cdt, cdn, "uom", matiere.uom);
			}
			if (!row.batch_no && matiere.batch_no) {
				frappe.model.set_value(cdt, cdn, "batch_no", matiere.batch_no);
			}
			frappe.model.set_value(cdt, cdn, "has_batch_no", matiere.has_batch_no);
		}
	},
});

frappe.ui.form.on("Checklist Preparation", {
	conforme(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.conforme) {
			frappe.model.set_value(cdt, cdn, "controle_par", frappe.session.user);
			frappe.model.set_value(cdt, cdn, "date_heure", frappe.datetime.now_datetime());
		}
	},
});

function charger_recette(frm) {
	if (!frm.doc.recette || !frm.doc.qty_prevue) {
		return;
	}
	frappe.call({
		method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.charger_recette",
		args: {
			recette: frm.doc.recette,
			qty_prevue: frm.doc.qty_prevue,
		},
		callback(r) {
			if (!r.message) {
				return;
			}
			frm.set_value("produit_fini", r.message.produit_fini);
			frm.set_value("uom", r.message.uom);
			frm.clear_table("matieres");
			(r.message.matieres || []).forEach((row) => {
				frm.add_child("matieres", row);
			});
			frm.refresh_field("matieres");
			refresh_all_stocks(frm);
			render_html_tables(frm);
		},
	});
}

function charger_checklist(frm) {
	if (!frm.doc.modele_checklist) {
		frm.clear_table("checklist");
		frm.refresh_field("checklist");
		render_html_tables(frm);
		return;
	}
	frappe.call({
		method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.charger_checklist",
		args: {
			modele_checklist: frm.doc.modele_checklist,
		},
		callback(r) {
			if (!r.message) {
				return;
			}
			frm.clear_table("checklist");
			(r.message || []).forEach((row) => {
				frm.add_child("checklist", row);
			});
			frm.refresh_field("checklist");
			render_html_tables(frm);
		},
	});
}

function warehouse_for_stock(frm, row) {
	const state = frm.doc.workflow_state;
	if (["Préparé", "En production"].includes(state) && frm.doc.warehouse_atelier) {
		return frm.doc.warehouse_atelier;
	}
	return row.warehouse;
}

function refresh_all_stocks(frm) {
	const rows = frm.doc.matieres || [];
	if (!rows.length) {
		return;
	}

	let pending = rows.length;
	const done = () => {
		pending -= 1;
		if (pending <= 0) {
			render_html_tables(frm);
			restore_clean_state(frm);
		}
	};

	rows.forEach((row) => {
		const warehouse = warehouse_for_stock(frm, row);
		if (!row.item_code || !warehouse) {
			row.stock_disponible = 0;
			done();
			return;
		}
		frappe.call({
			method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.get_stock_disponible",
			args: {
				item_code: row.item_code,
				warehouse: warehouse,
				batch_no: row.batch_no,
			},
			callback(r) {
				row.stock_disponible = r.message || 0;
				done();
			},
			error: done,
		});
	});
}

function refresh_stock(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const warehouse = warehouse_for_stock(frm, row);
	if (!row.item_code || !warehouse) {
		row.stock_disponible = 0;
		update_html_stock_cell(frm, cdn, 0);
		return;
	}
	frappe.call({
		method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.get_stock_disponible",
		args: {
			item_code: row.item_code,
			warehouse: warehouse,
			batch_no: row.batch_no,
		},
		callback(r) {
			row.stock_disponible = r.message || 0;
			update_html_stock_cell(frm, cdn, r.message || 0);
		},
	});
}

function update_html_stock_cell(frm, cdn, value) {
	const host = frm.fields_dict.interface_wizard;
	if (!host) {
		return;
	}
	host.$wrapper.find(`.ow-row[data-name="${cdn}"] .ow-stock`).text(value);
}

function restore_clean_state(frm) {
	if (!frm._ow_expect_clean) {
		return;
	}
	frm.doc.__unsaved = 0;
	if (frm.toolbar) {
		frm.toolbar.refresh();
	}
	toggle_save_button(frm);
}

function relax_lot_mandatory() {
	["Matiere Ordre Conditionnement", "Rebut Ordre Conditionnement"].forEach((dt) => {
		(frappe.meta.docfield_list[dt] || []).forEach((df) => {
			if (df.fieldname === "batch_no") {
				df.mandatory_depends_on = "";
				df.reqd = 0;
			}
		});
		const mapped = frappe.meta.docfield_map && frappe.meta.docfield_map[dt];
		if (mapped && mapped.batch_no) {
			mapped.batch_no.mandatory_depends_on = "";
			mapped.batch_no.reqd = 0;
		}
		const copies = frappe.meta.docfield_copy && frappe.meta.docfield_copy[dt];
		if (!copies) {
			return;
		}
		Object.values(copies).forEach((fields) => {
			const df = fields.batch_no;
			if (df) {
				df.mandatory_depends_on = "";
				df.reqd = 0;
			}
		});
	});
}

function activate_wizard_tab(frm) {
	if (frm._ordre_tech_mode) {
		return;
	}
	const field = frm.fields_dict.interface_wizard;
	if (field && field.tab && typeof field.tab.set_active === "function") {
		field.tab.set_active();
	}
}

function setup_wizard(frm) {
	const host = frm.fields_dict.interface_wizard;
	if (!host) {
		return;
	}

	$(frm.wrapper).addClass("ordre-wizard-form");
	frappe.require("/assets/unicare/css/ordre_conditionnement.css");
	restore_fields(frm);
	activate_wizard_tab(frm);

	if (frm._ordre_tech_mode) {
		$(frm.wrapper).addClass("tech-mode");
		render_tech_toggle(frm, wizard_host(frm));
		hide_native_workflow_buttons(frm);
		["matieres", "checklist", "rebuts"].forEach((fieldname) => frm.refresh_field(fieldname));
		return;
	}

	$(frm.wrapper).removeClass("tech-mode");
	host.$wrapper.show();
	render_wizard_shell(frm, wizard_host(frm));
	place_fields(frm);
	render_actions(frm);
	hide_native_workflow_buttons(frm);
	activate_wizard_tab(frm);
	setTimeout(() => {
		frm._ow_sync = false;
		restore_clean_state(frm);
		activate_wizard_tab(frm);
	}, 800);
}

function wizard_host(frm) {
	const $wrap = frm.fields_dict.interface_wizard.$wrapper;
	let $host = $wrap.find("> .ordre-wizard-host");
	if (!$host.length) {
		$host = $('<div class="ordre-wizard-host">').appendTo($wrap);
	}
	return $host;
}

function render_wizard_shell(frm, $host) {
	const state = frm.doc.workflow_state || "Brouillon";
	const product = __("Ordre de Conditionnement");
	const tech_link = frappe.user.has_role("System Manager")
		? `<button type="button" class="btn btn-sm btn-default ordre-wizard-tech">${__(
				"Formulaire technique"
		  )}</button>`
		: "";

	const steps = WIZARD_STEPS.map((step, idx) => {
		const cls = step_class(idx, state);
		const mark =
			cls === "ow-done"
				? `<span class="ow-num" aria-hidden="true">✓</span>`
				: `<span class="ow-num">${idx + 1}</span>`;
		return `<li class="${cls}">${mark}${frappe.utils.escape_html(step.label)}</li>`;
	}).join("");

	$host.html(`
		<div class="ordre-wizard">
			<div class="ordre-wizard-header">
				<h3 class="ordre-wizard-title">${frappe.utils.escape_html(product)}</h3>
				<div class="ordre-wizard-header-right">
					<div class="ordre-wizard-actions"></div>
					${tech_link}
				</div>
			</div>
			<div class="ordre-wizard-stepper">
				<ol class="ordre-wizard-steps">${steps}</ol>
			</div>
			<div class="ordre-wizard-panel">
				<h4>${frappe.utils.escape_html(panel_title(state))}</h4>
				${panel_hint(state)}
				${recap_html(frm)}
				<div class="ow-fields ow-main"></div>
				<div class="ow-html-tables">
					<div class="ow-tabs">
						<button type="button" class="ow-tab is-active" data-tab="production">${__("Matières")}</button>
						<button type="button" class="ow-tab" data-tab="checklist">${__("Checklist")}</button>
						<button type="button" class="ow-tab" data-tab="rebuts">${__("Rebuts")}</button>
						<button type="button" class="ow-tab" data-tab="warehouses">${__("Entrepôts")}</button>
						<button type="button" class="ow-tab" data-tab="transfers">${__("Transferts")}</button>
						<button type="button" class="ow-tab" data-tab="suivi">${__("Suivi")}</button>
					</div>
					<div class="ow-tab-panel" data-tab="production">
						<div class="ow-table-host" data-table="matieres"></div>
					</div>
					<div class="ow-tab-panel" data-tab="checklist" hidden>
						<div class="ow-table-host" data-table="checklist"></div>
					</div>
					<div class="ow-tab-panel" data-tab="rebuts" hidden>
						<div class="ow-table-host" data-table="rebuts"></div>
					</div>
					<div class="ow-tab-panel" data-tab="warehouses" hidden>
						<div class="ow-fields ow-warehouses"></div>
					</div>
					<div class="ow-tab-panel" data-tab="transfers" hidden>
						<div class="ow-stock-links"></div>
					</div>
					<div class="ow-tab-panel" data-tab="suivi" hidden>
						<div class="ow-table-host" data-table="suivi"></div>
					</div>
				</div>
			</div>
		</div>
	`);

	$host.find(".ordre-wizard-tech").on("click", (e) => {
		e.preventDefault();
		frm._ordre_tech_mode = true;
		setup_wizard(frm);
	});
	bind_table_tabs(frm, $host);
}

function render_tech_toggle(frm, $host) {
	$host.html(
		`<div class="ordre-wizard">
			<div class="ordre-wizard-header">
				<h3 class="ordre-wizard-title">${__("Formulaire technique")}</h3>
				<button type="button" class="btn btn-sm btn-default ordre-wizard-tech">${__(
					"Revenir à l'assistant"
				)}</button>
			</div>
		</div>`
	);
	$host.find(".ordre-wizard-tech").on("click", (e) => {
		e.preventDefault();
		frm._ordre_tech_mode = false;
		setup_wizard(frm);
	});
}

function step_class(idx, state) {
	if (state === "Terminé") {
		return "ow-done";
	}
	if (state === "Annulé") {
		return "";
	}
	const current = current_step_index(state);
	if (idx < current) {
		return "ow-done";
	}
	if (idx === current) {
		return "ow-current";
	}
	return "";
}

function current_step_index(state) {
	if (state === "Brouillon") {
		return 1;
	}
	if (state === "Préparé") {
		return 2;
	}
	if (state === "En production") {
		return 2;
	}
	if (state === "Terminé") {
		return 4;
	}
	return 1;
}

function panel_title(state) {
	if (state === "Brouillon") {
		return __("Préparer l'ordre");
	}
	if (state === "Préparé") {
		return __("Démarrer la production");
	}
	if (state === "En production") {
		return __("Saisir la clôture");
	}
	if (state === "Annulé") {
		return __("Ordre annulé");
	}
	return __("Ordre terminé");
}

function panel_hint(state) {
	if (state === "Brouillon") {
		return `<p class="ordre-wizard-hint">${__(
			"Renseignez les lots et la checklist, puis cliquez sur Préparer."
		)}</p>`;
	}
	if (state === "Préparé") {
		return `<p class="ordre-wizard-hint">${__(
			"Générez le lot produit fini puis démarrez la production."
		)}</p>`;
	}
	if (state === "En production") {
		return `<p class="ordre-wizard-hint">${__(
			"Saisissez les quantités réelles et clôturez l'ordre."
		)}</p>`;
	}
	return "";
}

function recap_html(frm) {
	const state = frm.doc.workflow_state;
	if (state !== "Terminé" && state !== "Annulé") {
		return "";
	}
	const fmt = (value) => (value == null || value === "" ? "—" : value);
	return `<div class="ordre-wizard-recap">
		<div><span>${__("Quantité prévue")}</span><b>${fmt(frm.doc.qty_prevue)}</b></div>
		<div><span>${__("Quantité réelle PF")}</span><b>${fmt(frm.doc.qty_reelle_pf)}</b></div>
		<div><span>${__("Rendement")}</span><b>${fmt(frm.doc.rendement_reel)}%</b></div>
	</div>`;
}

function fields_for_state(state) {
	const always = ["produit_fini", "nom_produit", "date_prevue", "modele_checklist"];
	if (state === "Brouillon") {
		return [...always, "recette", "qty_prevue", "uom"];
	}
	if (state === "Préparé") {
		return [...always, "lot_pf", "generer_lot_pf"];
	}
	if (state === "En production") {
		return [...always, "qty_reelle_pf", "rendement_reel", "lot_pf", "generer_lot_pf"];
	}
	return [...always, "lot_pf"];
}

function tables_for_state(_state) {
	return ["matieres", "checklist", "rebuts"];
}

function place_fields(frm) {
	const $main = frm.fields_dict.interface_wizard.$wrapper.find(".ow-main");
	const $wh = frm.fields_dict.interface_wizard.$wrapper.find(".ow-warehouses");
	if (!$main.length) {
		return;
	}

	fields_for_state(frm.doc.workflow_state || "Brouillon").forEach((fieldname) => {
		move_field(frm, fieldname, $main);
	});
	["warehouse_mp", "warehouse_conditionnement", "warehouse_atelier", "warehouse_pf", "warehouse_rebuts"].forEach(
		(fieldname) => {
			move_field(frm, fieldname, $wh);
		}
	);
	render_stock_links(frm);
	render_html_tables(frm);
	render_suivi_html(frm);
}

function move_field(frm, fieldname, $target) {
	const field = frm.fields_dict[fieldname];
	if (!field || !field.$wrapper) {
		return;
	}
	if (!field.$wrapper.data("ow-home")) {
		field.$wrapper.data("ow-home", field.$wrapper.parent());
	}
	const skip_label = ["Button", "HTML", "Table", "Section Break", "Column Break", "Tab Break"].includes(
		field.df.fieldtype
	);
	const $block = $(`<div class="ow-field" data-ow-field="${fieldname}"></div>`);
	if (!skip_label && field.df.label) {
		$block.append(
			`<label class="ow-label">${frappe.utils.escape_html(__(field.df.label))}</label>`
		);
	}
	field.$wrapper.appendTo($block);
	field.$wrapper.removeClass("hide-control").show();
	$block.appendTo($target);
}

function restore_fields(frm) {
	Object.values(frm.fields_dict).forEach((field) => {
		const $home = field.$wrapper && field.$wrapper.data("ow-home");
		if ($home && $home.length) {
			field.$wrapper.appendTo($home);
		}
	});
}

function render_stock_links(frm) {
	const $slot = frm.fields_dict.interface_wizard.$wrapper.find(".ow-stock-links");
	if (!$slot.length) {
		return;
	}
	const items = [
		{
			label: __("Transfert préparation"),
			doctype: "Stock Entry",
			name: frm.doc.stock_entry_preparation,
		},
		{
			label: __("Repack production"),
			doctype: "Stock Entry",
			name: frm.doc.stock_entry_production,
		},
		{
			label: __("Transfert rebuts"),
			doctype: "Stock Entry",
			name: frm.doc.stock_entry_rebuts,
		},
	];
	$slot.empty();
	items.forEach((item) => {
		if (!item.name) {
			$slot.append(
				`<div class="ow-stock-card"><span>${frappe.utils.escape_html(item.label)}</span><b>—</b></div>`
			);
			return;
		}
		const $card = $(
			`<a href="#" class="ow-stock-card is-link"><span>${frappe.utils.escape_html(
				item.label
			)}</span><b>${frappe.utils.escape_html(item.name)}</b></a>`
		);
		$card.on("click", (e) => {
			e.preventDefault();
			frappe.set_route("Form", item.doctype, item.name);
		});
		$slot.append($card);
	});
}

function render_suivi_html(frm) {
	const $slot = frm.fields_dict.interface_wizard.$wrapper.find('.ow-table-host[data-table="suivi"]');
	if (!$slot.length) {
		return;
	}
	const fmt_dt = (value) => (value ? frappe.datetime.str_to_user(value) : "—");
	const fmt_min = (value) => (value == null || value === "" ? "—" : value);
	const rows = [
		{
			label: __("Planifier"),
			dt: frm.doc.date_heure_planification,
			duree: frm.doc.duree_planification,
		},
		{
			label: __("Préparer"),
			dt: frm.doc.date_heure_preparation,
			duree: frm.doc.duree_preparation,
		},
		{
			label: __("Produire"),
			dt: frm.doc.date_heure_production,
			duree: frm.doc.duree_production,
		},
		{
			label: __("Clôturer"),
			dt: frm.doc.date_heure_cloture,
			duree: "",
		},
	];
	if (frm.doc.workflow_state === "Annulé" || frm.doc.date_heure_annulation) {
		rows.push({
			label: __("Annulation"),
			dt: frm.doc.date_heure_annulation,
			duree: "",
		});
	}
	const body = rows
		.map(
			(row) => `<tr>
			<td>${frappe.utils.escape_html(row.label)}</td>
			<td>${frappe.utils.escape_html(fmt_dt(row.dt))}</td>
			<td>${fmt_min(row.duree)}</td>
		</tr>`
		)
		.join("");
	$slot.html(`
		<div class="ow-table-block">
			<div class="ow-table-scroll">
				<table class="ow-table">
					<thead>
						<tr>
							<th>${__("Étape")}</th>
							<th>${__("Date / heure")}</th>
							<th>${__("Durée (min)")}</th>
						</tr>
					</thead>
					<tbody>
						${body}
						<tr>
							<td><b>${__("Total")}</b></td>
							<td>—</td>
							<td><b>${fmt_min(frm.doc.duree_totale)}</b></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	`);
}

function should_show_save(frm) {
	const state = frm.doc.workflow_state || "Brouillon";
	if (state === "Terminé" || state === "Annulé") {
		return false;
	}
	if (frm._ow_expect_clean) {
		return false;
	}
	return frm.is_dirty() || frm.is_new();
}

function toggle_save_button(frm) {
	const host = frm.fields_dict.interface_wizard;
	if (!host) {
		return;
	}
	host.$wrapper.find(".ordre-wizard-actions .ow-btn-save").toggle(should_show_save(frm));
}

function bind_save_visibility(frm) {
	if (frm._ow_save_bound) {
		return;
	}
	frm._ow_save_bound = true;
	$(frm.wrapper).on("dirty", () => {
		if (!frm._ow_sync) {
			frm._ow_expect_clean = false;
		}
		toggle_save_button(frm);
	});
}

function render_actions(frm) {
	const $actions = frm.fields_dict.interface_wizard.$wrapper.find(".ordre-wizard-actions");
	if (!$actions.length) {
		return;
	}
	$actions.empty();
	const state = frm.doc.workflow_state || "Brouillon";

	const add_btn = (label, style, handler) => {
		const $btn = $(`<button type="button" class="btn ${style}"></button>`).text(label);
		$btn.on("click", handler);
		$actions.append($btn);
	};

	if (state !== "Terminé" && state !== "Annulé") {
		const $save = $(`<button type="button" class="btn ow-btn-save"></button>`).text(__("Enregistrer"));
		$save.on("click", () => frm.save());
		$save.toggle(should_show_save(frm));
		$actions.append($save);
	}
	bind_save_visibility(frm);

	if (frm.is_new() && state === "Brouillon") {
		add_btn(__("Préparer"), "btn-primary", () => handle_workflow_action(frm, "Préparer"));
	}

	const paint_transitions = (transitions) => {
		const seen = new Set();
		(transitions || []).forEach((transition) => {
			if (seen.has(transition.action)) {
				return;
			}
			seen.add(transition.action);
			const danger = transition.action === "Annuler";
			add_btn(__(transition.action), danger ? "btn-danger" : "btn-primary", () => {
				handle_workflow_action(frm, transition.action);
			});
		});
	};

	if (!frm.is_new() && frappe.workflow && frappe.workflow.get_transitions) {
		frappe.workflow.get_transitions(frm.doc).then(paint_transitions);
	} else if (!frm.is_new()) {
		if (state === "Brouillon") {
			add_btn(__("Préparer"), "btn-primary", () => handle_workflow_action(frm, "Préparer"));
		}
		if (state === "Préparé") {
			add_btn(__("Démarrer la production"), "btn-primary", () =>
				handle_workflow_action(frm, "Démarrer la production")
			);
		}
		if (state === "En production") {
			add_btn(__("Clôturer"), "btn-primary", () => handle_workflow_action(frm, "Clôturer"));
		}
		if (
			["Brouillon", "Préparé", "En production"].includes(state) &&
			frappe.user.has_role("Responsable Conditionnement")
		) {
			add_btn(__("Annuler"), "btn-danger", () => handle_workflow_action(frm, "Annuler"));
		}
	}
}

function workflow_confirm_message(action) {
	if (action === "Préparer") {
		return __("Passer l'ordre en Préparé ? Les matières seront transférées vers l'atelier.");
	}
	if (action === "Démarrer la production") {
		return __("Démarrer la production ?");
	}
	if (action === "Clôturer") {
		return __("Clôturer cet ordre et générer les écritures de stock ?");
	}
	if (action === "Annuler") {
		return __("Annuler cet ordre et les écritures de stock liées ?");
	}
	return __("Confirmer le passage à l'étape « {0} » ?", [action]);
}

function handle_workflow_action(frm, action) {
	if (action === "Clôturer") {
		prompt_cloture(frm);
		return;
	}
	frappe.confirm(workflow_confirm_message(action), () => run_workflow(frm, action));
}

function prompt_cloture(frm) {
	const fields = [
		{
			fieldname: "qty_reelle_pf",
			label: __("Quantité réelle PF"),
			fieldtype: "Float",
			reqd: 1,
			non_negative: 1,
			default: flt(frm.doc.qty_reelle_pf) || flt(frm.doc.qty_prevue),
			description: frm.doc.uom || "",
		},
		{ fieldtype: "Section Break", label: __("Quantités réelles matières") },
	];

	(frm.doc.matieres || []).forEach((row) => {
		fields.push({
			fieldname: `qty_reelle__${row.name}`,
			label: [row.item_code, row.item_name].filter(Boolean).join(" — "),
			fieldtype: "Float",
			reqd: 1,
			non_negative: 1,
			default: flt(row.qty_reelle) || flt(row.qty_theorique),
			description: row.uom || "",
		});
	});

	fields.push({ fieldtype: "Section Break", label: __("Rebuts") });
	fields.push({
		fieldname: "qty_rebut",
		label: __("Quantité rebut"),
		fieldtype: "Float",
		non_negative: 1,
		default: flt(frm.doc.qty_rebut),
	});

	const dialog = new frappe.ui.Dialog({
		title: __("Clôturer l'ordre"),
		fields,
		primary_action_label: __("Valider"),
		primary_action(values) {
			if (flt(values.qty_reelle_pf) <= 0) {
				frappe.msgprint(__("Indiquez la quantité réelle de produit fini."));
				return;
			}
			dialog.hide();
			apply_cloture_quantities(frm, values).then(() => confirm_empty_rebuts(frm, values.qty_rebut));
		},
	});
	dialog.show();
}

function apply_cloture_quantities(frm, values) {
	frm._ow_expect_clean = false;
	const tasks = [frm.set_value("qty_reelle_pf", flt(values.qty_reelle_pf))];
	(frm.doc.matieres || []).forEach((row) => {
		const qty = values[`qty_reelle__${row.name}`];
		if (qty == null) {
			return;
		}
		tasks.push(frappe.model.set_value(row.doctype, row.name, "qty_reelle", flt(qty)));
	});
	return Promise.all(tasks);
}

function confirm_empty_rebuts(frm, qty_rebut) {
	const has_rebuts = (frm.doc.rebuts || []).some((row) => flt(row.qty) > 0);
	if (flt(qty_rebut) > 0 && !has_rebuts) {
		frappe.msgprint({
			title: __("Rebuts manquants"),
			indicator: "orange",
			message: __(
				"Vous avez saisi une quantité de rebut ({0}) mais la table des rebuts est vide. Ajoutez les lignes de rebuts (article, lot, quantité) ou mettez la quantité rebut à 0.",
				[flt(qty_rebut)]
			),
		});
		return;
	}
	let message = workflow_confirm_message("Clôturer");
	if (!has_rebuts) {
		message += "<br><br>" + __("La table des rebuts est vide. Confirmez-vous qu'il n'y a aucun rebut ?");
	}
	frappe.confirm(message, () => run_workflow(frm, "Clôturer"));
}

function run_workflow(frm, action) {
	const apply = () => {
		frappe.dom.freeze();
		frm.selected_workflow_action = action;
		return frm.script_manager
			.trigger("before_workflow_action")
			.then(() => frappe.xcall("frappe.model.workflow.apply_workflow", { doc: frm.doc, action }))
			.then((doc) => {
				frappe.model.sync(doc);
				frm.selected_workflow_action = null;
				frm.reload_doc();
				if (action === "Démarrer la production") {
					frappe.show_alert({
						message: __("Vous pouvez maintenant saisir la clôture."),
						indicator: "blue",
					});
				}
			})
			.finally(() => frappe.dom.unfreeze());
	};

	if (frm.is_new() || frm.is_dirty()) {
		return frm.save().then(apply);
	}
	return apply();
}

function hide_native_workflow_buttons(frm) {
	if (!frm.states) {
		return;
	}
	if (!frm._ordre_wizard_states_patched) {
		frm._ordre_wizard_states_patched = true;
		frm._ordre_native_show_actions = frm.states.show_actions.bind(frm.states);
		frm.states.show_actions = function () {
			if (frm._ordre_tech_mode) {
				return frm._ordre_native_show_actions();
			}
			this.frm.page.clear_actions_menu();
			this.frm.page.hide_actions_menu();
			this.frm.page.btn_primary.addClass("hide");
			this.frm.page.btn_secondary.addClass("hide");
			if (this.frm.page.actions_btn_group) {
				this.frm.page.actions_btn_group.addClass("hide");
			}
		};
	}
	frm.states.show_actions();
}

function render_html_tables(frm) {
	const host = frm.fields_dict.interface_wizard;
	if (!host || frm._ordre_tech_mode) {
		return;
	}
	const $wrap = host.$wrapper;
	if (!$wrap.find(".ow-html-tables").length) {
		return;
	}

	(frm._ow_controls || []).forEach((control) => {
		if (control && control.$wrapper) {
			control.$wrapper.remove();
		}
	});
	frm._ow_controls = [];

	const visible = tables_for_state(frm.doc.workflow_state || "Brouillon");
	["matieres", "checklist", "rebuts"].forEach((name) => {
		const $slot = $wrap.find(`.ow-table-host[data-table="${name}"]`);
		$slot.empty();
		if (!visible.includes(name)) {
			return;
		}
		if (name === "matieres") {
			render_matieres_html(frm, $slot);
		} else if (name === "checklist") {
			render_checklist_html(frm, $slot);
		} else {
			render_rebuts_html(frm, $slot);
		}
	});
}

function bind_table_tabs(frm, $host) {
	const activate = (name) => {
		frm._ow_table_tab = name;
		$host.find(".ow-tab").removeClass("is-active");
		$host.find(`.ow-tab[data-tab="${name}"]`).addClass("is-active");
		$host.find(".ow-tab-panel").each(function () {
			this.hidden = this.dataset.tab !== name;
		});
	};
	$host.find(".ow-tab").on("click", function () {
		activate(this.dataset.tab);
	});
	activate(frm._ow_table_tab || "production");
}

function wizard_readonly(frm) {
	return ["Terminé", "Annulé"].includes(frm.doc.workflow_state);
}

function render_matieres_html(frm, $slot) {
	const state = frm.doc.workflow_state || "Brouillon";
	const can_edit = state === "Brouillon" && !wizard_readonly(frm);
	const can_edit_reelle = state === "En production" && !wizard_readonly(frm);
	const show_reelle = ["En production", "Terminé", "Annulé"].includes(state);
	const rows = frm.doc.matieres || [];

	const head = `
		<tr>
			<th>${__("Article")}</th>
			<th>${__("Nom")}</th>
			<th>${__("Type")}</th>
			<th>${__("Lot")}</th>
			<th>${__("Qté théorique")}</th>
			${show_reelle ? `<th>${__("Qté réelle")}</th>` : ""}
			<th>${__("Unité")}</th>
			<th>${__("Stock")}</th>
			${can_edit ? `<th></th>` : ""}
		</tr>`;

	const body = rows
		.map((row) => {
			const lot_cell = `<td class="ow-lot" data-name="${row.name}"></td>`;
			const qty_th = can_edit
				? `<td><input type="number" min="0" step="0.001" class="form-control input-xs ow-qty" data-field="qty_theorique" data-name="${row.name}" value="${
						row.qty_theorique || 0
				  }"></td>`
				: `<td>${row.qty_theorique || 0}</td>`;
			const qty_re = show_reelle
				? can_edit_reelle
					? `<td><input type="number" min="0" step="0.001" class="form-control input-xs ow-qty" data-field="qty_reelle" data-name="${row.name}" value="${
							row.qty_reelle || 0
					  }"></td>`
					: `<td>${row.qty_reelle || 0}</td>`
				: "";
			const dup_btn = cint(row.has_batch_no)
				? `<button type="button" class="btn btn-xs btn-default ow-dup" data-name="${row.name}" title="${__(
						"Autre lot pour le même article"
				  )}">+ ${__("Lot")}</button>`
				: "";
			const actions = can_edit
				? `<td class="ow-row-actions">
					${dup_btn}
					<button type="button" class="btn btn-xs btn-default ow-del" data-name="${row.name}">×</button>
				</td>`
				: "";
			return `<tr class="ow-row" data-name="${row.name}">
				<td>${frappe.utils.escape_html(row.item_code || "")}</td>
				<td>${frappe.utils.escape_html(row.item_name || "")}</td>
				<td>${frappe.utils.escape_html(row.type_ingredient || "")}</td>
				${lot_cell}
				${qty_th}
				${qty_re}
				<td>${frappe.utils.escape_html(row.uom || "")}</td>
				<td class="ow-stock">${row.stock_disponible || 0}</td>
				${actions}
			</tr>`;
		})
		.join("");

	$slot.html(`
		<div class="ow-table-block">
			<h5>${__("Matières")}</h5>
			<div class="ow-table-scroll">
				<table class="ow-table">
					<thead>${head}</thead>
					<tbody>${body || `<tr><td colspan="9">${__("Aucune matière")}</td></tr>`}</tbody>
				</table>
			</div>
			${
				can_edit
					? `<button type="button" class="btn btn-sm btn-default ow-add-matiere">${__(
							"Ajouter une ligne"
					  )}</button>`
					: ""
			}
		</div>
	`);

	rows.forEach((row) => {
		const $cell = $slot.find(`.ow-lot[data-name="${row.name}"]`);
		mount_lot_control(frm, $cell, row, "Matiere Ordre Conditionnement", can_edit);
	});

	$slot.find(".ow-qty").on("change", function () {
		frm._ow_expect_clean = false;
		const name = this.dataset.name;
		const field = this.dataset.field;
		frappe.model.set_value("Matiere Ordre Conditionnement", name, field, this.value);
	});

	$slot.find(".ow-dup").on("click", function () {
		duplicate_matiere_row(frm, this.dataset.name);
	});

	$slot.find(".ow-del").on("click", function () {
		confirm_delete_matiere(frm, this.dataset.name);
	});

	$slot.find(".ow-add-matiere").on("click", () => add_matiere_row(frm));
}

function mount_lot_control(frm, $cell, row, doctype, editable) {
	if (!$cell.length) {
		return;
	}
	if (!cint(row.has_batch_no)) {
		$cell.text("—");
		return;
	}
	if (!editable) {
		$cell.text(row.batch_no || "—");
		return;
	}
	$cell.empty();
	const control = frappe.ui.form.make_control({
		parent: $cell.get(0),
		df: {
			fieldtype: "Link",
			options: "Batch",
			fieldname: "batch_no",
			placeholder: __("Lot"),
			only_input: true,
			get_query: () => ({
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: row.item_code,
					warehouse: warehouse_for_stock(frm, row),
				},
			}),
		},
		render_input: true,
		only_input: true,
	});
	let ignore_change = true;
	control.df.onchange = function () {
		if (ignore_change) {
			return;
		}
		const value = this.get_value() || "";
		if ((row.batch_no || "") === value) {
			return;
		}
		frm._ow_expect_clean = false;
		frappe.model.set_value(doctype, row.name, "batch_no", value);
	};
	control.set_value(row.batch_no || "");
	setTimeout(() => {
		ignore_change = false;
	}, 800);
	frm._ow_controls = frm._ow_controls || [];
	frm._ow_controls.push(control);
}

function confirm_delete_matiere(frm, name) {
	const row = (frm.doc.matieres || []).find((r) => r.name === name);
	if (!row) {
		return;
	}
	const label = [row.item_code, row.item_name].filter(Boolean).join(" — ") || name;
	frappe.confirm(__("Supprimer la ligne « {0} » ? Le document sera enregistré.", [label]), () => {
		remove_child_row(frm, "matieres", name);
		render_html_tables(frm);
		frm.save();
	});
}

function remove_child_row(frm, tablefield, name) {
	frm._ow_expect_clean = false;
	const cdt = frm.fields_dict[tablefield].df.options;
	frappe.model.clear_doc(cdt, name);
	frm.doc[tablefield] = (frm.doc[tablefield] || []).filter((row) => row.name !== name);
	(frm.doc[tablefield] || []).forEach((row, i) => {
		row.idx = i + 1;
	});
	frm.refresh_field(tablefield);
	frm.dirty();
}

function duplicate_matiere_row(frm, name) {
	frm._ow_expect_clean = false;
	const row = (frm.doc.matieres || []).find((r) => r.name === name);
	if (!row) {
		return;
	}
	frm.add_child("matieres", {
		item_code: row.item_code,
		item_name: row.item_name,
		type_ingredient: row.type_ingredient,
		has_batch_no: row.has_batch_no,
		uom: row.uom,
		warehouse: row.warehouse,
		qty_theorique: 0,
		qty_reelle: 0,
		batch_no: "",
	});
	frm.refresh_field("matieres");
	frm.dirty();
	render_html_tables(frm);
}

function add_matiere_row(frm) {
	frm._ow_expect_clean = false;
	const items = [...new Set((frm.doc.matieres || []).map((r) => r.item_code).filter(Boolean))];
	const d = new frappe.ui.Dialog({
		title: __("Ajouter une ligne matière"),
		fields: [
			{
				fieldname: "item_code",
				label: __("Article"),
				fieldtype: "Link",
				options: "Item",
				reqd: 1,
				get_query: () => {
					if (!items.length) {
						return { filters: { custom_type_conditionnement: ["in", ["Fût", "Conditionnement"]] } };
					}
					return { filters: { name: ["in", items] } };
				},
			},
			{
				fieldname: "qty_theorique",
				label: __("Quantité théorique"),
				fieldtype: "Float",
				reqd: 1,
			},
		],
		primary_action_label: __("Ajouter"),
		primary_action(values) {
			const source = (frm.doc.matieres || []).find((r) => r.item_code === values.item_code);
			frappe.db
				.get_value("Item", values.item_code, ["item_name", "has_batch_no", "stock_uom", "custom_type_conditionnement"])
				.then((r) => {
					const item = (r && r.message) || {};
					const type =
						item.custom_type_conditionnement === "Fût"
							? "Fût"
							: item.custom_type_conditionnement === "Conditionnement"
							? "Conditionnement"
							: source
							? source.type_ingredient
							: "";
					const warehouse =
						type === "Fût" ? frm.doc.warehouse_mp : frm.doc.warehouse_conditionnement;
					frm.add_child("matieres", {
						item_code: values.item_code,
						item_name: item.item_name || (source && source.item_name),
						type_ingredient: type,
						has_batch_no: item.has_batch_no,
						uom: item.stock_uom || (source && source.uom),
						warehouse: (source && source.warehouse) || warehouse,
						qty_theorique: values.qty_theorique,
						qty_reelle: values.qty_theorique,
					});
					frm.refresh_field("matieres");
					frm.dirty();
					d.hide();
					render_html_tables(frm);
					refresh_all_stocks(frm);
				});
		},
	});
	d.show();
}

function render_checklist_html(frm, $slot) {
	const can_edit = frm.doc.workflow_state === "Brouillon" && !wizard_readonly(frm);
	const rows = frm.doc.checklist || [];
	const body = rows
		.map((row) => {
			const check = can_edit
				? `<input type="checkbox" class="ow-check" data-name="${row.name}" ${
						cint(row.conforme) ? "checked" : ""
				  }>`
				: cint(row.conforme)
				? __("Oui")
				: __("Non");
			const observation = can_edit
				? `<input type="text" class="form-control input-xs ow-obs" data-name="${row.name}" value="${frappe.utils.escape_html(
						row.observation || ""
				  )}">`
				: frappe.utils.escape_html(row.observation || "—");
			return `<tr class="ow-row" data-name="${row.name}">
				<td>${frappe.utils.escape_html(row.controle || "")}</td>
				<td>${cint(row.obligatoire) ? __("Oui") : __("Non")}</td>
				<td>${check}</td>
				<td>${frappe.utils.escape_html(row.controle_par || "")}</td>
				<td>${row.date_heure || ""}</td>
				<td>${observation}</td>
			</tr>`;
		})
		.join("");

	$slot.html(`
		<div class="ow-table-block">
			<div class="ow-table-scroll">
				<table class="ow-table">
					<thead>
						<tr>
							<th>${__("Contrôle")}</th>
							<th>${__("Obligatoire")}</th>
							<th>${__("Conforme")}</th>
							<th>${__("Contrôlé par")}</th>
							<th>${__("Date / heure")}</th>
							<th>${__("Observation")}</th>
						</tr>
					</thead>
					<tbody>${body || `<tr><td colspan="6">${__("Aucune ligne")}</td></tr>`}</tbody>
				</table>
			</div>
		</div>
	`);

	$slot.find(".ow-check").on("change", function () {
		frm._ow_expect_clean = false;
		const name = this.dataset.name;
		const checked = this.checked ? 1 : 0;
		frappe.model.set_value("Checklist Preparation", name, "conforme", checked);
		if (checked) {
			frappe.model.set_value("Checklist Preparation", name, "controle_par", frappe.session.user);
			frappe.model.set_value("Checklist Preparation", name, "date_heure", frappe.datetime.now_datetime());
		}
		render_html_tables(frm);
	});
	$slot.find(".ow-obs").on("change", function () {
		frm._ow_expect_clean = false;
		frappe.model.set_value("Checklist Preparation", this.dataset.name, "observation", this.value);
	});
}

function render_rebuts_html(frm, $slot) {
	const can_edit = frm.doc.workflow_state === "En production" && !wizard_readonly(frm);
	const rows = frm.doc.rebuts || [];
	const body = rows
		.map((row) => {
			const qty = can_edit
				? `<input type="number" min="0" step="0.001" class="form-control input-xs ow-rebut-qty" data-name="${row.name}" value="${
						row.qty || 0
				  }">`
				: row.qty || 0;
			const del = can_edit
				? `<button type="button" class="btn btn-xs btn-default ow-del-rebut" data-name="${row.name}">×</button>`
				: "";
			return `<tr class="ow-row" data-name="${row.name}">
				<td>${frappe.utils.escape_html(row.item_code || "")}</td>
				<td>${frappe.utils.escape_html(row.item_name || "")}</td>
				<td class="ow-lot" data-name="${row.name}"></td>
				<td>${qty}</td>
				<td>${frappe.utils.escape_html(row.uom || "")}</td>
				<td>${del}</td>
			</tr>`;
		})
		.join("");

	$slot.html(`
		<div class="ow-table-block">
			<div class="ow-table-scroll">
				<table class="ow-table">
					<thead>
						<tr>
							<th>${__("Article")}</th>
							<th>${__("Nom")}</th>
							<th>${__("Lot")}</th>
							<th>${__("Quantité")}</th>
							<th>${__("Unité")}</th>
							<th></th>
						</tr>
					</thead>
					<tbody>${body || `<tr><td colspan="6">${__("Aucun rebut")}</td></tr>`}</tbody>
				</table>
			</div>
			${can_edit ? `<button type="button" class="btn btn-sm btn-default ow-add-rebut">${__("Ajouter un rebut")}</button>` : ""}
		</div>
	`);

	rows.forEach((row) => {
		const $cell = $slot.find(`tr[data-name="${row.name}"] .ow-lot`);
		mount_lot_control(frm, $cell, row, "Rebut Ordre Conditionnement", can_edit);
	});

	$slot.find(".ow-rebut-qty").on("change", function () {
		frappe.model.set_value("Rebut Ordre Conditionnement", this.dataset.name, "qty", this.value);
	});

	$slot.find(".ow-del-rebut").on("click", function () {
		remove_child_row(frm, "rebuts", this.dataset.name);
		render_html_tables(frm);
	});

	$slot.find(".ow-add-rebut").on("click", () => add_rebut_row(frm));
}

function add_rebut_row(frm) {
	frm._ow_expect_clean = false;
	const items = [...new Set((frm.doc.matieres || []).map((r) => r.item_code).filter(Boolean))];
	const d = new frappe.ui.Dialog({
		title: __("Ajouter un rebut"),
		fields: [
			{
				fieldname: "item_code",
				label: __("Article"),
				fieldtype: "Link",
				options: "Item",
				reqd: 1,
				get_query: () => ({ filters: { name: ["in", items.length ? items : [""]] } }),
			},
			{
				fieldname: "qty",
				label: __("Quantité"),
				fieldtype: "Float",
				reqd: 1,
			},
		],
		primary_action_label: __("Ajouter"),
		primary_action(values) {
			const matiere = (frm.doc.matieres || []).find((r) => r.item_code === values.item_code);
			frm.add_child("rebuts", {
				item_code: values.item_code,
				item_name: matiere && matiere.item_name,
				has_batch_no: matiere && matiere.has_batch_no,
				uom: matiere && matiere.uom,
				batch_no: matiere && matiere.batch_no,
				qty: values.qty,
			});
			frm.refresh_field("rebuts");
			frm.dirty();
			d.hide();
			render_html_tables(frm);
		},
	});
	d.show();
}
