"""Plans comptables livrés par Unicare (dossier verified/), lus comme ceux d'ERPNext."""

import json
import os
from pathlib import Path

import frappe

CHARTS_DIR = Path(__file__).parent / "verified"
SCF_CHART = "Algérie - SCF (Unicare)"


def _iter_chart_files(country_code=None, country_name=None):
	if not CHARTS_DIR.exists():
		return

	country_code = (country_code or "").lower()
	country_name = country_name or ""

	for fname in sorted(os.listdir(CHARTS_DIR)):
		fname = frappe.as_unicode(fname)
		if not fname.endswith(".json"):
			continue

		if country_code and not (
			fname.startswith(country_code) or (country_name and fname.startswith(country_name))
		):
			continue

		yield CHARTS_DIR / fname


def _load_chart_file(path):
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def get_unicare_chart_names(country):
	"""Plans Unicare actifs pour un pays, sans les plans Standard."""
	country_code = frappe.get_cached_value("Country", country, "code")
	if not country_code:
		return []

	charts = []
	for path in _iter_chart_files(country_code, country):
		content = _load_chart_file(path)
		if content.get("disabled", "No") == "No" or frappe.local.flags.allow_unverified_charts:
			charts.append(content["name"])

	return charts


def get_unicare_chart(chart_template):
	for path in _iter_chart_files():
		content = _load_chart_file(path)
		if content.get("name") == chart_template:
			return content

	return None


def get_unicare_chart_tree(chart_template):
	return (get_unicare_chart(chart_template) or {}).get("tree")


def get_unicare_defaults(chart_template):
	"""Champ de Company -> numéro de compte, pour un plan Unicare (vide sinon)."""
	return (get_unicare_chart(chart_template) or {}).get("unicare_defaults") or {}
