# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Temps réel du poste de bureau, branché sur `on_change` / `on_trash` des documents qu'il affiche (hooks.py).

Les comptes du bureau reçoivent `unicare_bureau_update` après le commit quand un document affiché change. Le message
ne porte que des identifiants : l'application recharge ensuite par l'API, qui applique les droits. Rien ici ne doit
bloquer une sauvegarde : une erreur est journalisée, jamais levée. Une liste ajoutée au bureau s'inscrit dans `WATCHED`
et dans `doc_events` de hooks.py.
"""

import frappe

from unicare.api.bureau_postes import BUREAU_ROLES

REALTIME_EVENT = "unicare_bureau_update"
_LOCAL_KEY = "unicare_bureau_realtime"

WATCHED = {"Customer", "Item", "Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "Payment Entry"}


def _muted():
	flags = frappe.flags
	return bool(flags.in_migrate or flags.in_patch or flags.in_install or flags.in_import or flags.in_test)


def recipients():
	"""Comptes actifs qui ont accès au poste de bureau."""
	members = frappe.get_all(
		"Has Role", filters={"role": ["in", list(BUREAU_ROLES)], "parenttype": "User"}, pluck="parent"
	)
	return frappe.get_all("User", filters={"name": ["in", members or [""]], "enabled": 1}, pluck="name")


def announce(doc, deleted=False):
	"""Un message par document dans la requête, envoyé après le commit."""
	sent = getattr(frappe.local, _LOCAL_KEY, None)
	if sent is None:
		sent = set()
		setattr(frappe.local, _LOCAL_KEY, sent)
	key = (doc.doctype, doc.name)
	if key in sent:
		return
	sent.add(key)
	message = {"doctype": doc.doctype, "name": doc.name, "by": frappe.session.user, "deleted": int(deleted)}
	for user in recipients():
		frappe.publish_realtime(REALTIME_EVENT, message, user=user, after_commit=True)


def on_change(doc, method=None):
	if doc.doctype not in WATCHED or _muted():
		return
	try:
		announce(doc)
	except Exception:
		frappe.log_error(title=f"Poste de bureau : événement {doc.doctype}")


def on_trash(doc, method=None):
	if doc.doctype not in WATCHED or _muted():
		return
	try:
		announce(doc, deleted=True)
	except Exception:
		frappe.log_error(title=f"Poste de bureau : suppression {doc.doctype}")
