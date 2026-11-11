# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Accueil du poste de bureau (/bureau) : la journée de la personne connectée.

- « À faire aujourd'hui » : une liste unique, tous modules, en trois groupes (en retard, aujourd'hui, à valider), chaque
  ligne avec l'action qui la règle ;
- « Pour vous » : ses notifications (mentions, alertes) ;
- « Le mois en bref » : un chiffre par module, repris des tableaux de bord ;
- « Repris récemment » : les dernières pièces qu'elle a modifiées.
Chaque bloc ne lit que les documents que son rôle peut lire (`frappe.get_list`).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, date_diff, flt, getdate, strip_html, today

from unicare.api.bureau_postes import require_bureau

LIMITE = 8

# Doctype → (module, fiche de l'interface, nature courte).
FICHES = {
	"Quotation": ("Ventes", "DevisFiche", "Devis"),
	"Sales Order": ("Ventes", "CommandeFiche", "Commande"),
	"Delivery Note": ("Ventes", "LivraisonFiche", "Livraison"),
	"Sales Invoice": ("Ventes", "FactureFiche", "Facture"),
	"Customer": ("Ventes", "Client", "Client"),
	"Supplier Quotation": ("Achats", "DevisFournisseurFiche", "Devis fourn."),
	"Purchase Order": ("Achats", "CommandeAchatFiche", "Commande"),
	"Purchase Receipt": ("Achats", "ReceptionFiche", "Réception"),
	"Purchase Invoice": ("Achats", "FactureAchatFiche", "Facture"),
	"Supplier": ("Achats", "Fournisseur", "Fournisseur"),
	"Payment Entry": ("Trésorerie", "PaiementFiche", "Paiement"),
	"Stock Entry": ("Stock", "MouvementFiche", "Mouvement"),
	"Stock Reconciliation": ("Stock", "InventaireFiche", "Inventaire"),
	"Batch": ("Stock", "Lot", "Lot"),
	"Item": ("Stock", "Article", "Article"),
	"Ordre de Conditionnement": ("Production", "OrdreFiche", "Ordre"),
	"Recette de Conditionnement": ("Production", "RecetteFiche", "Recette"),
}
# Brouillons repris dans « À valider » : le tiers affiché pour chacun.
BROUILLONS = {
	"Quotation": "customer_name",
	"Sales Order": "customer_name",
	"Delivery Note": "customer_name",
	"Sales Invoice": "customer_name",
	"Supplier Quotation": "supplier_name",
	"Purchase Order": "supplier_name",
	"Purchase Receipt": "supplier_name",
	"Purchase Invoice": "supplier_name",
	"Payment Entry": "party_name",
	"Stock Entry": "from_warehouse",
	"Stock Reconciliation": "set_warehouse",
}


def _readable(doctype):
	return bool(frappe.has_permission(doctype, "read"))


def _money(value):
	return f"{flt(value, 0):,.0f}".replace(",", " ") + " DA"


def _item(doctype, name, titre=None, detail=None, badge=None, ton="gray", action=None):
	module, fiche, nature = FICHES[doctype]
	return {
		"module": module,
		"nature": nature,
		"fiche": fiche,
		"name": name,
		"titre": titre or name,
		"detail": detail,
		"badge": badge,
		"ton": ton,
		"action": action or _("Ouvrir"),
	}


def _jours(day, jour):
	return _("{0} j").format(date_diff(jour, getdate(day)))


def _a_faire(jour):
	"""(en retard, aujourd'hui) : chaque ligne avec son action."""
	retard, aujourdhui = [], []

	if _readable("Sales Invoice"):
		for row in frappe.get_list(
			"Sales Invoice",
			filters=[["docstatus", "=", 1], ["outstanding_amount", ">", 0], ["due_date", "<=", jour]],
			fields=["name", "customer_name", "customer", "due_date", "outstanding_amount"],
			order_by="due_date asc",
			limit_page_length=LIMITE,
		):
			late = getdate(row.due_date) < jour
			item = _item(
				"Sales Invoice",
				row.name,
				f"{row.name} · {row.customer_name or row.customer}",
				_("{0} à encaisser, échue le {1}").format(_money(row.outstanding_amount), frappe.format(row.due_date, "Date")) if late else _("{0} à encaisser aujourd'hui").format(_money(row.outstanding_amount)),
				_jours(row.due_date, jour) if late else _("échéance"),
				"red" if late else "amber",
				_("Encaisser"),
			)
			(retard if late else aujourdhui).append(item)

	if _readable("Purchase Invoice"):
		for row in frappe.get_list(
			"Purchase Invoice",
			filters=[["docstatus", "=", 1], ["outstanding_amount", ">", 0], ["due_date", "<=", jour]],
			fields=["name", "supplier_name", "supplier", "due_date", "outstanding_amount"],
			order_by="due_date asc",
			limit_page_length=LIMITE,
		):
			late = getdate(row.due_date) < jour
			item = _item(
				"Purchase Invoice",
				row.name,
				f"{row.name} · {row.supplier_name or row.supplier}",
				_("{0} à payer").format(_money(row.outstanding_amount)),
				_jours(row.due_date, jour) if late else _("échéance"),
				"red" if late else "amber",
				_("Payer"),
			)
			item["module"] = "Trésorerie"
			(retard if late else aujourdhui).append(item)

	if _readable("Sales Order"):
		for row in frappe.get_list(
			"Sales Order",
			filters=[["docstatus", "=", 1], ["status", "in", ["To Deliver and Bill", "To Deliver"]], ["delivery_date", "<=", jour]],
			fields=["name", "customer_name", "customer", "delivery_date", "per_delivered"],
			order_by="delivery_date asc",
			limit_page_length=LIMITE,
		):
			late = getdate(row.delivery_date) < jour
			detail = _("Livraison prévue le {0}").format(frappe.format(row.delivery_date, "Date")) if late else _("Livraison prévue aujourd'hui")
			if flt(row.per_delivered):
				detail += _(" · livrée à {0} %").format(cint(row.per_delivered))
			item = _item("Sales Order", row.name, f"{row.name} · {row.customer_name or row.customer}", detail, _jours(row.delivery_date, jour) if late else _("à livrer"), "red" if late else "amber", _("Préparer le bon"))
			(retard if late else aujourdhui).append(item)

	if _readable("Purchase Order"):
		for row in frappe.get_list(
			"Purchase Order",
			filters=[["docstatus", "=", 1], ["status", "in", ["To Receive and Bill", "To Receive"]], ["schedule_date", "<=", jour]],
			fields=["name", "supplier_name", "supplier", "schedule_date"],
			order_by="schedule_date asc",
			limit_page_length=LIMITE,
		):
			late = getdate(row.schedule_date) < jour
			item = _item("Purchase Order", row.name, f"{row.name} · {row.supplier_name or row.supplier}", _("Réception attendue le {0}").format(frappe.format(row.schedule_date, "Date")) if late else _("Réception attendue aujourd'hui"), _jours(row.schedule_date, jour) if late else _("à recevoir"), "red" if late else "amber", _("Réceptionner"))
			(retard if late else aujourdhui).append(item)

	if _readable("Ordre de Conditionnement"):
		for row in frappe.get_list(
			"Ordre de Conditionnement",
			filters=[["workflow_state", "in", ["Brouillon", "Préparé", "En production"]], ["date_prevue", "<=", jour]],
			fields=["name", "workflow_state", "nom_produit", "qty_prevue", "uom", "date_prevue"],
			order_by="date_prevue asc",
			limit_page_length=LIMITE,
		):
			late = getdate(row.date_prevue) < jour
			state = row.workflow_state
			action = {"Brouillon": _("Planifier"), "Préparé": _("Démarrer"), "En production": _("Clôturer")}[state]
			etape = {"Brouillon": _("à planifier"), "Préparé": _("prêt à démarrer"), "En production": _("en production")}[state]
			item = _item("Ordre de Conditionnement", row.name, f"{row.name} · {row.nom_produit}", _("{0} {1} · {2}").format(cint(row.qty_prevue) if flt(row.qty_prevue).is_integer() else row.qty_prevue, row.uom or "", etape), _jours(row.date_prevue, jour) if late else etape, "red" if late else ("blue" if state == "Préparé" else "amber"), action)
			(retard if late else aujourdhui).append(item)

	if _readable("Batch") and _readable("Stock Entry"):
		from unicare.api.bureau_perimes import brouillons, lots_perimes

		deja = brouillons()
		vus = set()
		for lot, _article, depot, qty in lots_perimes():
			if lot in vus:
				continue
			vus.add(lot)
			draft = deja.get((lot, depot))
			designation = frappe.db.get_value("Batch", lot, "item_name") or _article
			if draft:
				retard.append(_item("Stock Entry", draft, _("Lot {0} · {1}").format(lot, designation), _("Périmé : déjà prévu dans le mouvement {0}, en brouillon").format(draft), _("périmé"), "red", _("Vérifier et valider")))
			else:
				retard.append(_item("Batch", lot, _("Lot {0} · {1}").format(lot, designation), _("Périmé, encore {0} en stock dans {1}").format(flt(qty, 3), depot), _("périmé"), "red", _("Mettre au rebut")))

	return retard, aujourdhui


def _a_valider(deja=()):
	"""Brouillons à valider, les derniers modifiés d'abord ; `deja` : ceux déjà listés plus haut (pas de doublon)."""
	rows = []
	for doctype, tiers in BROUILLONS.items():
		if not _readable(doctype):
			continue
		filters = [["docstatus", "=", 0]]
		if doctype == "Stock Entry":
			# Les mouvements d'un ordre de production se mènent depuis l'ordre.
			filters.append(["custom_ordre_conditionnement", "is", "not set"])
		fields = ["name", "modified", "owner", tiers] + (["to_warehouse"] if doctype == "Stock Entry" else [])
		for row in frappe.get_list(doctype, filters=filters, fields=fields, order_by="modified desc", limit_page_length=LIMITE):
			depuis = date_diff(today(), getdate(row.modified))
			if doctype == "Stock Entry":
				who = " → ".join(filter(None, [row.from_warehouse, row.to_warehouse]))
			else:
				who = cstr(row.get(tiers)).strip()[:60]
			detail = _("{0} en brouillon {1}").format(FICHES[doctype][2], _("aujourd'hui") if depuis <= 0 else _("depuis {0} j").format(depuis))
			if row.owner != frappe.session.user:
				detail += _(", créé par {0}").format(frappe.utils.get_fullname(row.owner))
			if row.name in deja:
				continue
			rows.append((row.modified, _item(doctype, row.name, f"{row.name}" + (f" · {who}" if who else ""), detail, _("brouillon"), "gray", _("Ouvrir"))))
	rows.sort(key=lambda item: item[0], reverse=True)
	return [item for _modified, item in rows]


def _pour_vous():
	user = frappe.session.user
	rows = frappe.get_all(
		"Notification Log",
		filters={"for_user": user},
		fields=["name", "subject", "type", "document_type", "document_name", "from_user", "read", "creation"],
		order_by="creation desc",
		limit_page_length=6,
	)
	items = []
	for row in rows:
		fiche = FICHES.get(row.document_type, (None, None, None))[1] if row.document_type else None
		items.append(
			{
				"name": row.name,
				"texte": strip_html(cstr(row.subject)).strip(),
				"type": "mention" if row.type == "Mention" else "alerte",
				"de": frappe.utils.get_fullname(row.from_user) if row.from_user else None,
				"lu": bool(cint(row.read)),
				"quand": str(row.creation),
				"fiche": fiche,
				"document": row.document_name if fiche else None,
				"module": FICHES.get(row.document_type, ("",))[0] if row.document_type else "",
			}
		)
	non_lus = frappe.db.count("Notification Log", {"for_user": user, "read": 0})
	return items, non_lus


def _recents():
	user = frappe.session.user
	rows = []
	for doctype in FICHES:
		if not _readable(doctype):
			continue
		title = {"Customer": "customer_name", "Supplier": "supplier_name", "Item": "item_name", "Batch": "item_name"}.get(doctype)
		fields = ["name", "modified"] + ([title] if title else [])
		for row in frappe.get_list(doctype, filters={"modified_by": user}, fields=fields, order_by="modified desc", limit_page_length=5):
			rows.append((row.modified, doctype, row))
	rows.sort(key=lambda item: item[0], reverse=True)
	result = []
	for modified, doctype, row in rows[:5]:
		module, fiche, nature = FICHES[doctype]
		result.append({"nature": nature, "fiche": fiche, "name": row.name, "libelle": row.get("customer_name") or row.get("supplier_name") or row.get("item_name") or None, "quand": str(modified)})
	return result


def _mois():
	"""Un chiffre par module, repris des tableaux de bord (période : ce mois)."""
	from unicare.api import bureau_tableaux as T

	p = T.periode("mois")
	wanted = [
		("ventes", "facture", "Ventes", "TableauVentes"),
		("ventes", "reste", "Ventes", "TableauVentes"),
		("achats", "achats", "Achats", "TableauAchats"),
		("stock", "valeur", "Stock", "TableauStock"),
		("production", "produit", "Production", "TableauProduction"),
	]
	cache, result = {}, []
	for module, key, label, page in wanted:
		try:
			if module not in cache:
				cache[module] = {row["key"]: row for row in T.BUILDERS[module](p)["indicateurs"]}
		except Exception:
			cache[module] = {}
		row = cache[module].get(key)
		if row:
			result.append({**row, "module": label, "tableau": page})
	return result


@frappe.whitelist()
def get_accueil():
	require_bureau()
	jour = getdate(today())
	retard, aujourdhui = _a_faire(jour)
	a_valider = _a_valider({item["name"] for item in retard + aujourdhui})
	pour_vous, non_lus = _pour_vous()
	return {
		"jour": str(jour),
		"prenom": (frappe.utils.get_fullname(frappe.session.user) or "").split(" ")[0],
		"a_faire": {
			"retard": retard[: LIMITE * 2],
			"aujourdhui": aujourdhui[: LIMITE * 2],
			"a_valider": a_valider[:LIMITE],
			"totaux": {"retard": len(retard), "aujourdhui": len(aujourdhui), "a_valider": len(a_valider)},
		},
		"pour_vous": pour_vous,
		"non_lus": non_lus,
		"recents": _recents(),
		"mois": _mois(),
	}


@frappe.whitelist(methods=["POST"])
def marquer_lus():
	require_bureau()
	for name in frappe.get_all("Notification Log", filters={"for_user": frappe.session.user, "read": 0}, pluck="name"):
		frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)
	return {"ok": True}
