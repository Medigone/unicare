import json
import os
from pathlib import Path

import frappe

CHARTS_DIR = Path(__file__).parent / "verified"


def _iter_chart_files(country_code=None, country_name=None):
	if not CHARTS_DIR.exists():
		return

	country_code = (country_code or "").lower()
	country_name = country_name or ""

	for fname in os.listdir(CHARTS_DIR):
		fname = frappe.as_unicode(fname)
		if not fname.endswith(".json"):
			continue

		if country_code and not (
			fname.startswith(country_code) or (country_name and fname.startswith(country_name))
		):
			continue

		yield CHARTS_DIR / fname


def _load_chart_file(path):
	with open(path) as f:
		return json.load(f)


def get_unicare_chart_names(country, with_standard=False):
	charts = []

	for path in _iter_chart_files(
		frappe.get_cached_value("Country", country, "code"),
		country,
	):
		content = _load_chart_file(path)
		if content.get("disabled", "No") == "No" or frappe.local.flags.allow_unverified_charts:
			charts.append(content["name"])

	if len(charts) != 1 or with_standard:
		charts += ["Standard", "Standard with Numbers"]

	return charts


def get_unicare_chart_tree(chart_template):
	for path in _iter_chart_files():
		content = _load_chart_file(path)
		if content.get("name") == chart_template:
			return content.get("tree") or {}

	return {}
