# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from unicare.conditionnement.constants import (
	CHECKLIST_DEFAUT,
	STATUT_ANNULE,
	STATUT_BROUILLON,
	STATUT_EN_PRODUCTION,
	STATUT_PREPARE,
	STATUT_TERMINE,
)
from unicare.conditionnement.stock import (
	cancel_stock_entry,
	create_stock_entry,
	ensure_batch,
	get_batch_available_qty,
	get_company,
	get_parametres,
	item_has_batch,
	make_fg_batch_name,
)


class OrdredeConditionnement(Document):
	def before_insert(self):
		self.set_defaults()
		self.ensure_checklist()

	def validate(self):
		self.set_defaults()
		self.ensure_checklist()
		self.calculate_rendement()
		self.validate_quantities()
		self.validate_state()

	def on_update(self):
		if self.flags.ignore_stock_events:
			return

		previous = self.get_doc_before_save()
		old_state = previous.workflow_state if previous else STATUT_BROUILLON
		new_state = self.workflow_state or STATUT_BROUILLON
		if old_state == new_state:
			return

		self.handle_state_change(old_state, new_state)

	def set_defaults(self):
		parametres = get_parametres()
		if not self.warehouse_mp:
			self.warehouse_mp = parametres.warehouse_mp
		if not self.warehouse_conditionnement:
			self.warehouse_conditionnement = parametres.warehouse_conditionnement
		if not self.warehouse_atelier:
			self.warehouse_atelier = parametres.warehouse_atelier
		if not self.warehouse_pf:
			self.warehouse_pf = parametres.warehouse_pf
		if not self.warehouse_rebuts:
			self.warehouse_rebuts = parametres.warehouse_rebuts
		if not self.workflow_state:
			self.workflow_state = STATUT_BROUILLON

	def ensure_checklist(self):
		if self.checklist:
			return
		for row in CHECKLIST_DEFAUT:
			self.append("checklist", row)

	def calculate_rendement(self):
		if flt(self.qty_prevue) > 0 and flt(self.qty_reelle_pf) > 0:
			self.rendement_reel = flt(self.qty_reelle_pf) / flt(self.qty_prevue) * 100
		else:
			self.rendement_reel = 0

	def validate_quantities(self):
		if flt(self.qty_prevue) <= 0:
			frappe.throw(_("La quantité prévue doit être supérieure à 0."))

	def validate_state(self):
		previous = self.get_doc_before_save()
		old_state = previous.workflow_state if previous else None
		new_state = self.workflow_state or STATUT_BROUILLON
		if old_state == new_state:
			return

		if new_state == STATUT_PREPARE:
			self.validate_preparation()
		elif new_state == STATUT_EN_PRODUCTION:
			if old_state != STATUT_PREPARE and not self.stock_entry_preparation:
				frappe.throw(_("La préparation doit être validée avant de démarrer la production."))
		elif new_state == STATUT_TERMINE:
			if old_state not in (STATUT_EN_PRODUCTION, STATUT_PREPARE):
				frappe.throw(_("Clôture impossible depuis l'état {0}.").format(old_state or STATUT_BROUILLON))
			self.validate_cloture()

	def validate_preparation(self):
		self.validate_warehouses()
		self.validate_recette_active()
		self.validate_checklist()
		self.validate_matieres_for_preparation()

	def validate_warehouses(self):
		missing = []
		if not self.warehouse_atelier:
			missing.append(_("Atelier"))
		if not self.warehouse_pf:
			missing.append(_("Magasin produits finis"))
		if missing:
			frappe.throw(_("Renseignez les entrepôts : {0}").format(", ".join(missing)))

	def validate_recette_active(self):
		if not self.recette:
			frappe.throw(_("Sélectionnez une recette."))
		if not frappe.db.get_value("Recette de Conditionnement", self.recette, "actif"):
			frappe.throw(_("La recette {0} n'est pas active.").format(self.recette))

	def validate_checklist(self):
		if not self.checklist:
			frappe.throw(_("La checklist de préparation est vide."))
		for row in self.checklist:
			if cint(row.obligatoire) and not cint(row.conforme):
				frappe.throw(
					_("Le contrôle obligatoire « {0} » n'est pas conforme.").format(row.controle)
				)

	def validate_matieres_for_preparation(self):
		if not self.matieres:
			frappe.throw(_("Aucune matière n'est définie. Chargez la recette."))

		for row in self.matieres:
			if flt(row.qty_theorique) <= 0:
				frappe.throw(_("Quantité théorique manquante pour {0}.").format(row.item_code))
			if not row.warehouse:
				frappe.throw(_("Indiquez le magasin source pour {0}.").format(row.item_code))
			if item_has_batch(row.item_code) and not row.batch_no:
				frappe.throw(_("Indiquez le lot pour {0}.").format(row.item_code))

			qty_needed = flt(row.qty_theorique)
			if item_has_batch(row.item_code):
				available = get_batch_available_qty(row.item_code, row.warehouse, row.batch_no)
				if available + 0.0001 < qty_needed:
					frappe.throw(
						_("Stock insuffisant pour {0} / lot {1} : {2} disponible, {3} requis.").format(
							row.item_code, row.batch_no, available, qty_needed
						)
					)
			else:
				available = flt(
					frappe.db.get_value(
						"Bin",
						{"item_code": row.item_code, "warehouse": row.warehouse},
						"actual_qty",
					)
				)
				if available + 0.0001 < qty_needed:
					frappe.throw(
						_("Stock insuffisant pour {0} : {1} disponible, {2} requis.").format(
							row.item_code, available, qty_needed
						)
					)

	def validate_cloture(self):
		if flt(self.qty_reelle_pf) <= 0:
			frappe.throw(_("Indiquez la quantité réelle de produit fini avant de clôturer."))
		if not self.matieres:
			frappe.throw(_("Aucune matière consommée."))
		for row in self.matieres:
			if flt(row.qty_reelle) <= 0:
				frappe.throw(_("Indiquez la quantité réelle consommée pour {0}.").format(row.item_code))
			if item_has_batch(row.item_code) and not row.batch_no:
				frappe.throw(_("Le lot est obligatoire pour {0}.").format(row.item_code))

		self.warn_rendement()

	def warn_rendement(self):
		parametres = get_parametres()
		tolerance = flt(parametres.rendement_tolerance_pct) or 10
		theorique = flt(frappe.db.get_value("Recette de Conditionnement", self.recette, "rendement_theorique")) or 100
		ecart = abs(flt(self.rendement_reel) - theorique)
		if ecart > tolerance:
			frappe.msgprint(
				_(
					"Le rendement réel ({0} %) s'écarte de plus de {1} % du rendement théorique ({2} %)."
				).format(flt(self.rendement_reel, 2), tolerance, theorique),
				indicator="orange",
				alert=True,
			)

	def handle_state_change(self, old_state, new_state):
		if new_state == STATUT_PREPARE:
			self.create_preparation_transfer()
		elif new_state == STATUT_TERMINE:
			self.create_production_repack()
		elif new_state == STATUT_ANNULE:
			self.cancel_linked_stock_entries()

	def create_preparation_transfer(self):
		if self.stock_entry_preparation:
			return

		items = []
		for row in self.matieres:
			items.append(
				{
					"item_code": row.item_code,
					"qty": row.qty_theorique,
					"uom": row.uom,
					"s_warehouse": row.warehouse,
					"t_warehouse": self.warehouse_atelier,
					"batch_no": row.batch_no,
				}
			)

		se = create_stock_entry(
			purpose="Material Transfer",
			items=items,
			company=get_company(),
			remarks=_("Préparation {0}").format(self.name),
			ordre=self.name,
		)
		self.db_set("stock_entry_preparation", se.name)

	def create_production_repack(self):
		if self.stock_entry_production:
			return

		if not self.lot_pf:
			lot_pf = ensure_batch(
				item_code=self.produit_fini,
				batch_no=make_fg_batch_name(self.produit_fini),
				origine="Production",
				ordre=self.name,
			)
			self.db_set("lot_pf", lot_pf)
			self.lot_pf = lot_pf
		else:
			ensure_batch(
				item_code=self.produit_fini,
				batch_no=self.lot_pf,
				origine="Production",
				ordre=self.name,
			)

		items = []
		for row in self.matieres:
			items.append(
				{
					"item_code": row.item_code,
					"qty": row.qty_reelle or row.qty_theorique,
					"uom": row.uom,
					"s_warehouse": self.warehouse_atelier,
					"batch_no": row.batch_no,
					"is_finished_item": 0,
				}
			)

		qty_pf = flt(self.qty_reelle_pf)
		qty_rebut = flt(self.qty_rebut)
		qty_to_produce = qty_pf + qty_rebut if self.warehouse_rebuts and qty_rebut > 0 else qty_pf

		items.append(
			{
				"item_code": self.produit_fini,
				"qty": qty_to_produce,
				"uom": self.uom,
				"t_warehouse": self.warehouse_pf,
				"batch_no": self.lot_pf,
				"is_finished_item": 1,
			}
		)

		se = create_stock_entry(
			purpose="Repack",
			items=items,
			company=get_company(),
			remarks=_("Production {0}").format(self.name),
			ordre=self.name,
		)
		self.db_set("stock_entry_production", se.name)

		if qty_rebut > 0 and self.warehouse_rebuts:
			rebuts = create_stock_entry(
				purpose="Material Transfer",
				items=[
					{
						"item_code": self.produit_fini,
						"qty": self.qty_rebut,
						"uom": self.uom,
						"s_warehouse": self.warehouse_pf,
						"t_warehouse": self.warehouse_rebuts,
						"batch_no": self.lot_pf,
					}
				],
				company=get_company(),
				remarks=_("Rebuts {0}").format(self.name),
				ordre=self.name,
			)
			self.db_set("stock_entry_rebuts", rebuts.name)

	def cancel_linked_stock_entries(self):
		for field in ("stock_entry_rebuts", "stock_entry_production", "stock_entry_preparation"):
			se_name = self.get(field)
			if se_name:
				cancel_stock_entry(se_name)
				self.db_set(field, None)


@frappe.whitelist()
def charger_recette(recette, qty_prevue):
	if not recette:
		frappe.throw(_("Sélectionnez une recette."))

	doc = frappe.get_doc("Recette de Conditionnement", recette)
	if not cint(doc.actif):
		frappe.throw(_("La recette {0} n'est pas active.").format(recette))

	qty_prevue = flt(qty_prevue)
	if qty_prevue <= 0:
		frappe.throw(_("Indiquez une quantité prévue."))

	factor = qty_prevue / flt(doc.quantite_base)
	parametres = get_parametres()
	rows = []
	for ing in doc.ingredients:
		warehouse = (
			parametres.warehouse_mp if ing.type_ingredient == "Fût" else parametres.warehouse_conditionnement
		)
		rows.append(
			{
				"item_code": ing.item_code,
				"item_name": ing.item_name,
				"type_ingredient": ing.type_ingredient,
				"has_batch_no": 1 if item_has_batch(ing.item_code) else 0,
				"qty_theorique": flt(ing.qty) * factor,
				"qty_reelle": flt(ing.qty) * factor,
				"uom": ing.uom,
				"warehouse": warehouse,
				"stock_disponible": get_stock_disponible(ing.item_code, warehouse) if warehouse else 0,
			}
		)

	return {
		"produit_fini": doc.produit_fini,
		"uom": doc.uom,
		"matieres": rows,
	}


@frappe.whitelist()
def generer_lot_pf(produit_fini, ordre=None):
	if not produit_fini:
		frappe.throw(_("Sélectionnez d'abord le produit fini."))

	if not frappe.db.exists("Item", produit_fini):
		frappe.throw(_("Article {0} introuvable.").format(produit_fini))

	if not item_has_batch(produit_fini):
		frappe.throw(_("L'article {0} n'est pas suivi par lot.").format(produit_fini))

	batch_no = make_fg_batch_name(produit_fini)
	return ensure_batch(
		item_code=produit_fini,
		batch_no=batch_no,
		origine="Production",
		ordre=ordre,
	)


@frappe.whitelist()
def get_stock_disponible(item_code, warehouse, batch_no=None):
	if batch_no:
		return get_batch_available_qty(item_code, warehouse, batch_no)
	return flt(
		frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
	)
