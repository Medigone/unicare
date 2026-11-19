# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Les nombres et les dates tels qu'ils s'écrivent sur une pièce algérienne : « 756 840,00 », « 19/11/2026 »,
et la somme en toutes lettres (« sept cent cinquante-six mille huit cent quarante dinars algériens et zéro
centime »)."""

from frappe.utils import flt, getdate
from num2words import num2words

ESPACE = chr(0x202F)  # espace fine insécable : le séparateur des milliers ne se coupe pas en fin de ligne
INSECABLE = chr(0xA0)
MOINS = chr(0x2212)


def _milliers(entier):
	return f"{entier:,}".replace(",", ESPACE)


def montant(valeur, decimales=2):
	"""756840 → « 756 840,00 » ; les négatifs gardent leur signe moins."""
	valeur = flt(valeur, decimales)
	signe = MOINS + INSECABLE if valeur < 0 else ""
	entier, _, fraction = f"{abs(valeur):.{decimales}f}".partition(".")
	texte = _milliers(int(entier))
	return f"{signe}{texte},{fraction}" if decimales else f"{signe}{texte}"


def quantite(valeur):
	"""1000 → « 1 000 » ; 2.5 → « 2,5 » : pas de décimales inutiles."""
	valeur = flt(valeur, 3)
	if valeur == int(valeur):
		return montant(valeur, 0)
	return montant(valeur, 3).rstrip("0").rstrip(",")


def taux(valeur):
	"""19.0 → « 19 % » ; 9.5 → « 9,5 % »."""
	return f"{quantite(valeur)}{INSECABLE}%"


def date_fr(valeur):
	return getdate(valeur).strftime("%d/%m/%Y") if valeur else ""


def en_lettres(valeur, monnaie="dinars algériens", unite="dinar algérien"):
	"""La somme en toutes lettres, dinars et centimes : la mention « Arrêtée la présente facture à la somme de »."""
	valeur = abs(flt(valeur, 2))
	dinars = int(valeur)
	centimes = round((valeur - dinars) * 100)
	texte_dinars = f"{num2words(dinars, lang='fr')} {unite if dinars <= 1 else monnaie}"
	# « un million de dinars » : de devant le nom après million(s) et milliard(s) tout ronds
	if dinars >= 1_000_000 and dinars % 1_000_000 == 0:
		texte_dinars = f"{num2words(dinars, lang='fr')} de {monnaie}"
	texte_centimes = (
		"zéro centime"
		if not centimes
		else f"{num2words(centimes, lang='fr')} centime{'s' if centimes > 1 else ''}"
	)
	return f"{texte_dinars} et {texte_centimes}"
