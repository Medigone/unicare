# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime, time_diff_in_seconds

from unicare.conditionnement.constants import (
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
	get_lots_fournisseur_from_matieres,
	get_parametres,
	item_has_batch,
	make_fg_batch_name,
)


class OrdredeConditionnement(Document):
	def before_insert(self):
		self.set_defaults()
		self.apply_recette()
		self.apply_checklist()

	def validate(self):
		self.set_defaults()
		self.apply_checklist()
		self.calculate_qty_rebut()
		self.calculate_qty_complement()
		self.calculate_rendement()
		self.stamp_step_times()
		self.validate_quantities()
		self.validate_planning_fields_locked()
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

	def apply_recette(self):
		if self.matieres or not self.recette or flt(self.qty_prevue) <= 0:
			return
		data = charger_recette(self.recette, self.qty_prevue)
		self.produit_fini = data.get("produit_fini")
		if data.get("uom"):
			self.uom = data.get("uom")
		for row in data.get("matieres") or []:
			self.append("matieres", row)

	def apply_checklist(self):
		if not self.modele_checklist:
			return

		state = self.workflow_state or STATUT_BROUILLON
		previous = self.get_doc_before_save() if not self.is_new() else None
		model_changed = bool(previous and previous.modele_checklist != self.modele_checklist)

		if model_changed and state != STATUT_BROUILLON:
			frappe.throw(_("Impossible de changer le modèle de checklist après la planification."))

		if self.checklist and not (model_changed and state == STATUT_BROUILLON):
			return

		self.set("checklist", [])
		for row in charger_checklist(self.modele_checklist):
			self.append("checklist", row)

	def stamp_step_times(self, now=None):
		now = now or now_datetime()
		if not self.date_heure_planification:
			self.date_heure_planification = now
		if self.is_new():
			return
		previous = self.get_doc_before_save()
		old_state = (previous.workflow_state if previous else STATUT_BROUILLON) or STATUT_BROUILLON
		new_state = self.workflow_state or STATUT_BROUILLON
		if old_state == new_state:
			return
		apply_step_stamps(self, old_state, new_state, now)

	def calculate_qty_rebut(self):
		self.qty_rebut = sum(flt(row.qty) for row in self.rebuts)

	def calculate_qty_complement(self):
		totals = defaultdict(float)
		for row in self.complements:
			totals[_item_lot_key(row.item_code, row.batch_no)] += flt(row.qty)
		for row in self.matieres:
			row.qty_complement = totals.get(_item_lot_key(row.item_code, row.batch_no), 0)

	def calculate_rendement(self):
		if flt(self.qty_prevue) > 0 and flt(self.qty_reelle_pf) > 0:
			self.rendement_reel = flt(self.qty_reelle_pf) / flt(self.qty_prevue) * 100
		else:
			self.rendement_reel = 0

	def validate_quantities(self):
		if flt(self.qty_prevue) <= 0:
			frappe.throw(_("La quantité prévue doit être supérieure à 0."))

	def validate_planning_fields_locked(self):
		if self.is_new():
			return
		state = self.workflow_state or STATUT_BROUILLON
		if state == STATUT_BROUILLON:
			return
		locked = {
			"date_prevue": _("La date prévue ne peut être modifiée qu'en Brouillon."),
			"recette": _("La recette ne peut être modifiée qu'en Brouillon."),
			"qty_prevue": _("La quantité prévue ne peut être modifiée qu'en Brouillon."),
		}
		for fieldname, message in locked.items():
			if self.has_value_changed(fieldname):
				frappe.throw(message)

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
		self.validate_checklist_modele()
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

	def validate_checklist_modele(self):
		if not self.modele_checklist:
			frappe.throw(_("Sélectionnez un modèle de checklist."))
		if not frappe.db.get_value("Checklist Ordre Conditionnement", self.modele_checklist, "actif"):
			frappe.throw(_("Le modèle de checklist {0} n'est pas actif.").format(self.modele_checklist))

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
		if item_has_batch(self.produit_fini) and not self.lot_pf:
			frappe.throw(_("Générez ou sélectionnez le lot produit fini avant de clôturer."))
		if not self.matieres:
			frappe.throw(_("Aucune matière consommée."))
		for row in self.matieres:
			if flt(row.qty_reelle) <= 0:
				frappe.throw(_("Indiquez la quantité réelle consommée pour {0}.").format(row.item_code))
			if item_has_batch(row.item_code) and not row.batch_no:
				frappe.throw(_("Le lot est obligatoire pour {0}.").format(row.item_code))

		self.validate_rebuts()
		self.validate_cloture_quantities()
		self.warn_rendement()

	def validate_rebuts(self):
		if self.rebuts and not self.warehouse_rebuts:
			frappe.throw(_("Renseignez le magasin rebuts pour enregistrer les rebus matières."))

		matiere_items = {row.item_code for row in self.matieres}
		for row in self.rebuts:
			if flt(row.qty) <= 0:
				frappe.throw(_("La quantité de rebut de {0} doit être supérieure à 0.").format(row.item_code))
			if row.item_code not in matiere_items:
				frappe.throw(
					_("Le rebut {0} doit correspondre à une matière de l'ordre.").format(row.item_code)
				)
			if item_has_batch(row.item_code) and not row.batch_no:
				frappe.throw(_("Indiquez le lot pour le rebut {0}.").format(row.item_code))

	def validate_cloture_quantities(self):
		prepared = defaultdict(float)
		consumed = defaultdict(float)
		for row in self.matieres:
			key = _item_lot_key(row.item_code, row.batch_no)
			prepared[key] += flt(row.qty_theorique)
			consumed[key] += flt(row.qty_reelle)

		for row in self.complements:
			key = _item_lot_key(row.item_code, row.batch_no)
			prepared[key] += flt(row.qty)

		scrap = defaultdict(float)
		for row in self.rebuts:
			key = _item_lot_key(row.item_code, row.batch_no)
			scrap[key] += flt(row.qty)

		keys = set(prepared) | set(consumed) | set(scrap)
		for key in keys:
			item_code, batch_no = key
			used = consumed.get(key, 0) + scrap.get(key, 0)
			label = f"{item_code} / {batch_no}" if batch_no else item_code
			available_prepared = prepared.get(key, 0)
			if used > available_prepared + 0.0001:
				frappe.throw(
					_(
						"Quantité consommée + rebut ({0}) supérieure à la quantité préparée + compléments ({1}) pour {2}. Utilisez « Complément de matières » pour transférer le manque depuis le magasin."
					).format(used, available_prepared, label)
				)

			if not self.warehouse_atelier or used <= 0:
				continue
			if item_has_batch(item_code):
				available = get_batch_available_qty(item_code, self.warehouse_atelier, batch_no)
			else:
				available = flt(
					frappe.db.get_value(
						"Bin",
						{"item_code": item_code, "warehouse": self.warehouse_atelier},
						"actual_qty",
					)
				)
			if available + 0.0001 < used:
				frappe.throw(
					_("Stock atelier insuffisant pour {0} : {1} disponible, {2} requis.").format(
						label, available, used
					)
				)

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
			self.create_rebuts_transfer()
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

		lot_fournisseur = get_lots_fournisseur_from_matieres(self.matieres)
		qty_produite = flt(self.qty_reelle_pf)
		if not self.lot_pf:
			lot_pf = ensure_batch(
				item_code=self.produit_fini,
				batch_no=make_fg_batch_name(self.produit_fini),
				lot_fournisseur=lot_fournisseur,
				origine="Production",
				ordre=self.name,
				qty_produite=qty_produite,
			)
			self.db_set("lot_pf", lot_pf)
			self.lot_pf = lot_pf
		else:
			ensure_batch(
				item_code=self.produit_fini,
				batch_no=self.lot_pf,
				lot_fournisseur=lot_fournisseur,
				origine="Production",
				ordre=self.name,
				qty_produite=qty_produite,
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

		items.append(
			{
				"item_code": self.produit_fini,
				"qty": flt(self.qty_reelle_pf),
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

	def create_rebuts_transfer(self):
		if self.stock_entry_rebuts or not self.rebuts:
			return

		items = []
		for row in self.rebuts:
			items.append(
				{
					"item_code": row.item_code,
					"qty": row.qty,
					"uom": row.uom,
					"s_warehouse": self.warehouse_atelier,
					"t_warehouse": self.warehouse_rebuts,
					"batch_no": row.batch_no,
				}
			)

		se = create_stock_entry(
			purpose="Material Transfer",
			items=items,
			company=get_company(),
			remarks=_("Rebuts matières {0}").format(self.name),
			ordre=self.name,
		)
		self.db_set("stock_entry_rebuts", se.name)

	def cancel_linked_stock_entries(self):
		for field in ("stock_entry_rebuts", "stock_entry_production"):
			se_name = self.get(field)
			if se_name:
				cancel_stock_entry(se_name)
				self.db_set(field, None)

		for row in self.complements:
			if row.stock_entry:
				cancel_stock_entry(row.stock_entry)
				row.db_set("stock_entry", None)

		if self.stock_entry_preparation:
			cancel_stock_entry(self.stock_entry_preparation)
			self.db_set("stock_entry_preparation", None)

	def add_complement(self, item_code, qty, warehouse=None, batch_no=None):
		state = self.workflow_state or STATUT_BROUILLON
		if state not in (STATUT_PREPARE, STATUT_EN_PRODUCTION):
			frappe.throw(
				_("Un complément n'est possible qu'en Préparé ou En production (état actuel : {0}).").format(
					state
				)
			)
		if not self.stock_entry_preparation:
			frappe.throw(_("La préparation doit être validée avant d'ajouter un complément."))
		if not self.warehouse_atelier:
			frappe.throw(_("Renseignez l'entrepôt atelier."))

		qty = flt(qty)
		if qty <= 0:
			frappe.throw(_("La quantité du complément doit être supérieure à 0."))
		if not item_code:
			frappe.throw(_("Sélectionnez un article."))

		matiere_rows = [row for row in self.matieres if row.item_code == item_code]
		if not matiere_rows:
			frappe.throw(
				_("Le complément {0} doit correspondre à une matière de l'ordre.").format(item_code)
			)

		template = matiere_rows[0]
		fallback_warehouse = (
			self.warehouse_mp if template.type_ingredient == "Fût" else self.warehouse_conditionnement
		)
		warehouse = warehouse or template.warehouse or fallback_warehouse
		if not warehouse:
			frappe.throw(_("Indiquez le magasin source pour {0}.").format(item_code))

		if item_has_batch(item_code) and not batch_no:
			frappe.throw(_("Indiquez le lot pour {0}.").format(item_code))

		available = get_stock_disponible(item_code, warehouse, batch_no if item_has_batch(item_code) else None)
		if available + 0.0001 < qty:
			label = f"{item_code} / {batch_no}" if batch_no else item_code
			frappe.throw(
				_("Stock insuffisant pour {0} : {1} disponible, {2} requis.").format(label, available, qty)
			)

		se = create_stock_entry(
			purpose="Material Transfer",
			items=[
				{
					"item_code": item_code,
					"qty": qty,
					"uom": template.uom,
					"s_warehouse": warehouse,
					"t_warehouse": self.warehouse_atelier,
					"batch_no": batch_no if item_has_batch(item_code) else None,
				}
			],
			company=get_company(),
			remarks=_("Complément {0}").format(self.name),
			ordre=self.name,
		)

		matched = _find_matiere_row(self, item_code, batch_no)
		if not matched:
			self.append(
				"matieres",
				{
					"item_code": item_code,
					"item_name": template.item_name,
					"type_ingredient": template.type_ingredient,
					"has_batch_no": template.has_batch_no,
					"qty_theorique": 0,
					"qty_reelle": qty,
					"uom": template.uom,
					"warehouse": warehouse,
					"batch_no": batch_no if item_has_batch(item_code) else None,
				},
			)

		self.append(
			"complements",
			{
				"item_code": item_code,
				"item_name": template.item_name,
				"has_batch_no": template.has_batch_no,
				"qty": qty,
				"uom": template.uom,
				"warehouse": warehouse,
				"batch_no": batch_no if item_has_batch(item_code) else None,
				"stock_entry": se.name,
			},
		)
		self.calculate_qty_complement()
		self.flags.ignore_stock_events = True
		try:
			self.save()
		except Exception:
			cancel_stock_entry(se.name)
			raise
		return se


@frappe.whitelist()
def ajouter_complement(ordre, item_code, qty, warehouse=None, batch_no=None):
	if not ordre:
		frappe.throw(_("Ordre manquant."))

	doc = frappe.get_doc("Ordre de Conditionnement", ordre)
	doc.check_permission("write")
	se = doc.add_complement(item_code, qty, warehouse=warehouse, batch_no=batch_no)
	return se.name


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
def charger_checklist(modele_checklist):
	if not modele_checklist:
		frappe.throw(_("Sélectionnez un modèle de checklist."))

	doc = frappe.get_doc("Checklist Ordre Conditionnement", modele_checklist)
	if not cint(doc.actif):
		frappe.throw(_("Le modèle de checklist {0} n'est pas actif.").format(modele_checklist))
	if not doc.lignes:
		frappe.throw(_("Le modèle de checklist {0} n'a aucune ligne.").format(modele_checklist))

	return [{"controle": row.controle, "obligatoire": cint(row.obligatoire)} for row in doc.lignes]


@frappe.whitelist()
def generer_lot_pf(produit_fini, ordre=None):
	if not produit_fini:
		frappe.throw(_("Sélectionnez d'abord le produit fini."))

	if not frappe.db.exists("Item", produit_fini):
		frappe.throw(_("Article {0} introuvable.").format(produit_fini))

	if not item_has_batch(produit_fini):
		frappe.throw(_("L'article {0} n'est pas suivi par lot.").format(produit_fini))

	lot_fournisseur = None
	if ordre and frappe.db.exists("Ordre de Conditionnement", ordre):
		oc = frappe.get_doc("Ordre de Conditionnement", ordre)
		lot_fournisseur = get_lots_fournisseur_from_matieres(oc.matieres)

	batch_no = make_fg_batch_name(produit_fini)
	return ensure_batch(
		item_code=produit_fini,
		batch_no=batch_no,
		lot_fournisseur=lot_fournisseur,
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


def _item_lot_key(item_code, batch_no):
	if item_has_batch(item_code):
		return (item_code, batch_no or "")
	return (item_code, "")


def _find_matiere_row(doc, item_code, batch_no=None):
	has_batch = item_has_batch(item_code)
	for row in doc.matieres:
		if row.item_code != item_code:
			continue
		if has_batch and (row.batch_no or "") != (batch_no or ""):
			continue
		return row
	return None


def _minutes_between(start, end):
	if not start or not end:
		return 0
	return cint(time_diff_in_seconds(end, start) / 60)


def apply_step_stamps(doc, old_state, new_state, now):
	if old_state == new_state:
		return

	if new_state == STATUT_PREPARE:
		if not doc.date_heure_preparation:
			doc.date_heure_preparation = now
			doc.duree_planification = _minutes_between(doc.date_heure_planification, now)
	elif new_state == STATUT_EN_PRODUCTION:
		if not doc.date_heure_production:
			doc.date_heure_production = now
			doc.duree_preparation = _minutes_between(doc.date_heure_preparation, now)
	elif new_state == STATUT_TERMINE:
		if not doc.date_heure_cloture:
			doc.date_heure_cloture = now
			if old_state == STATUT_EN_PRODUCTION:
				doc.duree_production = _minutes_between(doc.date_heure_production, now)
			elif old_state == STATUT_PREPARE:
				doc.duree_preparation = _minutes_between(doc.date_heure_preparation, now)
			doc.duree_totale = _minutes_between(doc.date_heure_planification, now)
	elif new_state == STATUT_ANNULE:
		if not doc.date_heure_annulation:
			doc.date_heure_annulation = now
			doc.duree_totale = _minutes_between(doc.date_heure_planification, now)
