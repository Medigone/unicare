"""Société : plans et taxes Unicare disponibles avant la création des comptes, comptes par défaut après."""

from unicare.chart_of_accounts.patch import apply_patches


def ensure_patches(doc, method=None):
	apply_patches()


def apply_unicare_defaults(doc, method=None):
	"""À la création seulement : ERPNext a déjà créé les comptes et choisi des défauts au hasard par type."""
	if not doc.flags.in_insert:
		return

	from unicare.setup.algeria import appliquer_defaults

	appliquer_defaults(doc, force=True)
