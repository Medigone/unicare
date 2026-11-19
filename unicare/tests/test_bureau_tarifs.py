# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from unicare.api import bureau_achats, bureau_devis
from unicare.api import bureau_tarifs as T
from unicare.api import tarifs_calcules as calcul


def _article(nom, vendu=1, achete=1):
	"""Un article d'essai, retrouvé par sa désignation : son code suit le type (AU-…)."""
	existing = frappe.db.get_value("Item", {"item_name": nom}, "name")
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": nom,
				"item_name": nom,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": frappe.db.get_value("UOM", {"enabled": 1}, "name"),
				"is_sales_item": vendu,
				"is_purchase_item": achete,
				"custom_type_conditionnement": "Autre",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _tarif(nom, sens):
	if not frappe.db.exists("Price List", nom):
		T.create_tarif(nom, sens)
	return nom


class TestTarifs(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.vente = _tarif("Tarif essai vente", "vente")
		self.achat = _tarif("Tarif essai achat", "achat")
		self.article = _article("Essai tarif zircon")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _ligne(self, liste, search="Essai tarif zircon"):
		return next(row for row in T.get_prix(liste, search)["lignes"] if row["article"] == self.article)

	def test_poser_changer_retirer_un_prix(self):
		ligne = self._ligne(self.vente)
		self.assertIsNone(ligne["prix"])
		ligne = T.set_prix(self.vente, self.article, "1 250,50")
		self.assertEqual(ligne["prix"], 1250.5)
		self.assertEqual(ligne["unite_prix"], frappe.db.get_value("Item", self.article, "stock_uom"))
		ligne = T.set_prix(self.vente, self.article, "1300", ligne["modified"])
		self.assertEqual(self._ligne(self.vente)["prix"], 1300)
		ligne = T.set_prix(self.vente, self.article, "", ligne["modified"])
		self.assertIsNone(ligne["prix"])
		self.assertFalse(
			frappe.db.exists("Item Price", {"price_list": self.vente, "item_code": self.article})
		)

	def test_prix_refuses(self):
		for prix in ("0", "-5", "abc"):
			with self.assertRaises(frappe.ValidationError):
				T.set_prix(self.vente, self.article, prix)
		ligne = T.set_prix(self.vente, self.article, "100")
		with self.assertRaises(frappe.TimestampMismatchError):
			T.set_prix(self.vente, self.article, "200", "2000-01-01 00:00:00")
		with self.assertRaises(frappe.TimestampMismatchError):
			T.set_prix(self.vente, self.article, "200")
		self.assertEqual(self._ligne(self.vente)["prix"], ligne["prix"])

	def test_vues_et_sens(self):
		seulement_vendu = _article("Essai tarif zircon vendu", vendu=1, achete=0)
		T.set_prix(self.vente, self.article, "100")
		reponse = T.get_prix(self.vente, "Essai tarif zircon", "sans_prix")
		self.assertEqual([row["article"] for row in reponse["lignes"]], [seulement_vendu])
		self.assertEqual(
			{key: reponse["compte"][key] for key in ("tous", "sans_prix", "avec_prix")},
			{"tous": 2, "sans_prix": 1, "avec_prix": 1},
		)
		self.assertNotIn("ecart", reponse["compte"])
		self.assertEqual(
			[row["article"] for row in T.get_prix(self.achat, "Essai tarif zircon")["lignes"]], [self.article]
		)
		with self.assertRaises(frappe.ValidationError):
			T.get_prix(self.vente, vue="inconnue")

	def test_la_ligne_modifiee_est_celle_que_lisent_les_pieces(self):
		uom = frappe.db.get_value("Item", self.article, "stock_uom")
		for rate, debut, fin in ((10, "2026-01-01", "2026-05-31"), (20, "2026-06-01", None)):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": self.vente,
					"item_code": self.article,
					"uom": uom,
					"price_list_rate": rate,
					"valid_from": debut,
					"valid_upto": fin,
				}
			).insert()
		ligne = self._ligne(self.vente)
		self.assertEqual(ligne["prix"], 20)
		T.set_prix(self.vente, self.article, "25", ligne["modified"])
		with patch.object(bureau_devis, "_price_list", return_value=self.vente):
			self.assertEqual(bureau_devis._prices([self.article])[self.article], 25)

	def test_tarif_par_defaut(self):
		T.set_prix(self.achat, self.article, "40")
		reglages = T.set_tarif_defaut("achat", self.achat)
		self.assertEqual(reglages["defauts"]["achat"], self.achat)
		self.assertEqual(bureau_achats.buying_price_list(), self.achat)
		self.assertEqual(bureau_achats.buying_prices([self.article])[self.article], 40)
		T.set_tarif_defaut("vente", self.vente)
		self.assertEqual(bureau_devis._price_list(), self.vente)
		with self.assertRaises(frappe.ValidationError):
			T.set_tarif_defaut("vente", self.achat)

	def test_creation_de_tarif(self):
		with self.assertRaises(frappe.ValidationError):
			T.create_tarif(self.vente, "vente")
		with self.assertRaises(frappe.ValidationError):
			T.create_tarif("  ", "vente")
		with self.assertRaises(frappe.ValidationError):
			T.create_tarif("Tarif essai autre", "location")
		tarifs = T.create_tarif("Tarif essai revendeurs", "vente")
		row = next(row for row in tarifs["tarifs"] if row["name"] == "Tarif essai revendeurs")
		self.assertEqual((row["sens"], row["prix"], row["defaut"]), ("vente", 0, False))

	def test_fiche_article(self):
		with (
			patch.object(T, "_price_list", return_value=self.vente),
			patch.object(T, "buying_price_list", return_value=self.achat),
		):
			T.set_prix(self.vente, self.article, "90")
			prix = T.prix_article(self.article)
		self.assertEqual(prix["vente"], {"tarif": self.vente, "prix": 90, "concerne": True})
		self.assertIsNone(prix["achat"]["prix"])

	def test_sans_droit(self):
		def refus(*args, throw=False, **kwargs):
			if throw:
				frappe.throw("Refusé", frappe.PermissionError)
			return False

		with patch("frappe.has_permission", side_effect=refus):
			self.assertIsNone(T.prix_article(self.article))
			with self.assertRaises(frappe.PermissionError):
				T.get_tarifs()


def _tiers(doctype):
	"""Un client ou un fournisseur existant, ou None (le test qui en a besoin est alors sauté)."""
	return frappe.db.get_value(doctype, {"disabled": 0}, "name")


class TestPeriodesDePrix(FrappeTestCase):
	"""Plusieurs lignes de prix pour un article dans un même tarif : périodes, tiers, activation du tarif."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.vente = _tarif("Tarif essai vente", "vente")
		self.achat = _tarif("Tarif essai achat", "achat")
		self.article = _article("Essai tarif périodes")
		self.uom = frappe.db.get_value("Item", self.article, "stock_uom")
		self.today = nowdate()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _ligne(self, liste, debut, fin=None, prix=10, **extra):
		return frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": liste,
				"item_code": self.article,
				"uom": self.uom,
				"price_list_rate": prix,
				"valid_from": debut,
				"valid_upto": fin,
				**extra,
			}
		).insert()

	def _resume(self, liste, **kwargs):
		reponse = T.get_prix(liste, "Essai tarif périodes", **kwargs)
		return next(row for row in reponse["lignes"] if row["article"] == self.article)

	def test_prix_en_vigueur_selon_la_date(self):
		self._ligne(self.vente, add_days(self.today, -60), add_days(self.today, -31), prix=80)
		self._ligne(self.vente, add_days(self.today, -30), add_days(self.today, 10), prix=90)
		self._ligne(self.vente, add_days(self.today, 11), prix=100)
		ligne = self._resume(self.vente)
		self.assertEqual(ligne["prix"], 90)
		self.assertTrue(ligne["expire_bientot"])
		self.assertEqual(ligne["a_venir"], {"prix": 100, "debut": add_days(self.today, 11)})
		self.assertEqual((ligne["nb_a_venir"], ligne["nb_anciens"], ligne["nb_lignes"]), (1, 1, 3))
		self.assertEqual(self._resume(self.vente, date=add_days(self.today, 20))["prix"], 100)
		self.assertEqual(self._resume(self.vente, date=add_days(self.today, -45))["prix"], 80)
		self.assertIsNone(self._resume(self.vente, date=add_days(self.today, -90))["prix"])
		with patch.object(bureau_devis, "_price_list", return_value=self.vente):
			self.assertEqual(bureau_devis._prices([self.article])[self.article], 90)
			self.assertEqual(
				bureau_devis._prices([self.article], date=add_days(self.today, 20))[self.article], 100
			)
		self.assertEqual(
			[row["article"] for row in T.get_prix(self.vente, "Essai tarif périodes", "a_venir")["lignes"]],
			[self.article],
		)

	def test_sans_prix_en_vigueur_le_dernier_expire_est_signale(self):
		self._ligne(self.vente, add_days(self.today, -60), add_days(self.today, -1), prix=70)
		ligne = self._resume(self.vente)
		self.assertIsNone(ligne["prix"])
		self.assertEqual(ligne["dernier_expire"], {"prix": 70, "fin": add_days(self.today, -1)})

	def test_prix_reserve_a_un_client(self):
		client = _tiers("Customer")
		if not client:
			self.skipTest("Aucun client sur ce site.")
		self._ligne(self.vente, add_days(self.today, -10), prix=100)
		self._ligne(self.vente, add_days(self.today, -5), prix=85, customer=client)
		ligne = self._resume(self.vente)
		self.assertEqual((ligne["prix"], ligne["nb_tiers"]), (100, 1))
		with patch.object(bureau_devis, "_price_list", return_value=self.vente):
			self.assertEqual(bureau_devis._prices([self.article])[self.article], 100)
			self.assertEqual(bureau_devis._prices([self.article], client)[self.article], 85)
			self.assertEqual(bureau_devis._prices([self.article], "Un autre client")[self.article], 100)
		statuts = {row["prix"]: row["statut"] for row in T.get_lignes(self.vente, self.article)["lignes"]}
		self.assertEqual(statuts, {100: "vigueur", 85: "tiers"})

	def test_prix_d_achat_d_un_fournisseur(self):
		fournisseur = _tiers("Supplier")
		if not fournisseur:
			self.skipTest("Aucun fournisseur sur ce site.")
		self._ligne(self.achat, add_days(self.today, -10), prix=50)
		self._ligne(self.achat, add_days(self.today, -10), prix=45, supplier=fournisseur)
		with patch.object(bureau_achats, "buying_price_list", return_value=self.achat):
			self.assertEqual(bureau_achats.buying_prices([self.article])[self.article], 50)
			self.assertEqual(bureau_achats.buying_prices([self.article], fournisseur)[self.article], 45)

	def test_nouveau_prix_a_partir_d_une_date_clot_le_precedent(self):
		ancien = self._ligne(self.vente, add_days(self.today, -30), prix=90)
		debut = add_days(self.today, 15)
		lignes = T.save_ligne(
			self.vente, self.article, {"prix": "1 000,5", "debut": debut, "note": "Hausse"}, clore=1
		)
		self.assertEqual(
			frappe.db.get_value("Item Price", ancien.name, "valid_upto"),
			frappe.utils.getdate(add_days(debut, -1)),
		)
		par_prix = {row["prix"]: row for row in lignes["lignes"]}
		self.assertEqual(par_prix[1000.5]["statut"], "a_venir")
		self.assertEqual(par_prix[1000.5]["note"], "Hausse")
		self.assertEqual(par_prix[90]["statut"], "vigueur")
		self.assertEqual(self._resume(self.vente, date=debut)["prix"], 1000.5)

	def test_modifier_et_supprimer_une_ligne(self):
		ligne = self._ligne(self.vente, add_days(self.today, -30), prix=90)
		with self.assertRaises(frappe.TimestampMismatchError):
			T.save_ligne(
				self.vente, self.article, {"prix": 95, "debut": self.today}, ligne.name, "2000-01-01"
			)
		with self.assertRaises(frappe.ValidationError):
			T.save_ligne(
				self.vente,
				self.article,
				{"prix": 95, "debut": self.today, "fin": add_days(self.today, -1)},
				ligne.name,
				str(ligne.modified),
			)
		with self.assertRaises(frappe.ValidationError):
			T.save_ligne(self.vente, self.article, {"prix": "", "debut": self.today})
		lignes = T.save_ligne(
			self.vente,
			self.article,
			{"prix": 95, "debut": add_days(self.today, -30)},
			ligne.name,
			str(ligne.modified),
		)
		self.assertEqual([row["prix"] for row in lignes["lignes"]], [95])
		lignes = T.delete_ligne(self.vente, ligne.name, lignes["lignes"][0]["modified"])
		self.assertEqual(lignes["lignes"], [])

	def test_la_case_de_prix_modifie_le_prix_en_vigueur(self):
		self._ligne(self.vente, add_days(self.today, -30), prix=90)
		futur = self._ligne(self.vente, add_days(self.today, 30), prix=120)
		ligne = self._resume(self.vente)
		ligne = T.set_prix(self.vente, self.article, "92", ligne["modified"])
		self.assertEqual(ligne["prix"], 92)
		self.assertEqual(frappe.db.get_value("Item Price", futur.name, "price_list_rate"), 120)

	def test_reprendre_les_derniers_prix_payes(self):
		frappe.db.set_value("Item", self.article, "last_purchase_rate", 33)
		self.assertEqual(self._resume(self.achat)["ecart"], None)
		self.assertEqual(T.reprendre_derniers_prix(self.achat, [self.article]), {"crees": 1})
		self.assertEqual(self._resume(self.achat)["prix"], 33)
		self.assertEqual(T.reprendre_derniers_prix(self.achat, [self.article]), {"crees": 0})
		with self.assertRaises(frappe.ValidationError):
			T.reprendre_derniers_prix(self.vente)

	def test_ecart_avec_le_dernier_prix_paye(self):
		frappe.db.set_value("Item", self.article, "last_purchase_rate", 110)
		self._ligne(self.achat, add_days(self.today, -5), prix=100)
		ligne = self._resume(self.achat)
		self.assertEqual(ligne["ecart"], 0.1)
		reponse = T.get_prix(self.achat, "Essai tarif périodes", "ecart")
		self.assertEqual([row["article"] for row in reponse["lignes"]], [self.article])

	def test_activer_desactiver_un_tarif(self):
		tarifs = T.set_tarif_actif(self.vente, 0)
		row = next(row for row in tarifs["tarifs"] if row["name"] == self.vente)
		self.assertFalse(row["actif"])
		self.assertEqual(T.get_prix(self.vente, "Essai tarif périodes")["tarif"]["actif"], False)
		with self.assertRaises(frappe.ValidationError):
			T.set_prix(self.vente, self.article, "10")
		T.set_tarif_actif(self.vente, 1)
		T.set_tarif_defaut("vente", self.vente)
		with self.assertRaises(frappe.ValidationError):
			T.set_tarif_actif(self.vente, 0)


class TestTarifCalcule(FrappeTestCase):
	"""Un tarif créé à partir d'un autre, avec une remise, et qui suit son tarif de base."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.base = _tarif("Tarif essai base", "vente")
		self.article = _article("Essai tarif calculé")
		self.autre = _article("Essai tarif calculé bis")
		self.uom = frappe.db.get_value("Item", self.article, "stock_uom")
		self.today = nowdate()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _prix(self, article, prix, debut, fin=None, liste=None):
		return frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": liste or self.base,
				"item_code": article,
				"uom": frappe.db.get_value("Item", article, "stock_uom"),
				"price_list_rate": prix,
				"valid_from": debut,
				"valid_upto": fin,
			}
		).insert()

	def _creer(self, nom="Tarif essai remise", **kwargs):
		params = {"base": self.base, "ajustement": "remise", "pourcentage": 10, "arrondi": 1, **kwargs}
		return T.create_tarif(nom, "vente", **params)

	def _taux(self, liste, article):
		return {
			row.valid_from and str(row.valid_from): row.price_list_rate
			for row in frappe.get_all(
				"Item Price",
				filters={"price_list": liste, "item_code": article},
				fields=["valid_from", "price_list_rate"],
			)
		}

	def test_calcul_et_arrondi(self):
		self.assertEqual(calcul.calculer(1450, "remise", 10, 1), 1305)
		self.assertEqual(calcul.calculer(95, "remise", 10, 1), 86)
		self.assertEqual(calcul.calculer(95, "remise", 10, 0), 85.5)
		self.assertEqual(calcul.calculer(640, "majoration", 15, 10), 740)
		self.assertEqual(calcul.calculer(180, "aucun", 0, 0), 180)
		with self.assertRaises(frappe.ValidationError):
			calcul.verifier_regle("remise", 100, 1)
		with self.assertRaises(frappe.ValidationError):
			calcul.verifier_regle("rabais", 10, 1)

	def test_copie_avec_remise_et_prix_a_venir(self):
		self._prix(self.article, 1450, add_days(self.today, -30))
		self._prix(self.article, 1520, add_days(self.today, 40))
		self._prix(self.autre, 95, add_days(self.today, -60), add_days(self.today, -1))
		reglages = self._creer()
		self.assertEqual(reglages["crees"], 2)
		row = next(row for row in reglages["tarifs"] if row["name"] == "Tarif essai remise")
		self.assertEqual(row["base"], self.base)
		self.assertEqual(
			self._taux("Tarif essai remise", self.article),
			{self.today: 1305, add_days(self.today, 40): 1368},
		)
		self.assertEqual(self._taux("Tarif essai remise", self.autre), {})
		self.assertEqual(T.get_changements("Tarif essai remise")["changements"], [])

	def test_sans_prix_a_venir_ni_lien(self):
		self._prix(self.article, 1450, add_days(self.today, -30))
		self._prix(self.article, 1520, add_days(self.today, 40))
		reglages = self._creer("Tarif essai copie", a_venir=0, lien=0)
		self.assertEqual(reglages["crees"], 1)
		self.assertIsNone(calcul.regle("Tarif essai copie"))
		with self.assertRaises(frappe.ValidationError):
			T.get_changements("Tarif essai copie")

	def test_changements_du_tarif_de_base(self):
		source = self._prix(self.article, 1450, add_days(self.today, -30))
		autre = self._prix(self.autre, 95, add_days(self.today, -30))
		self._creer()
		liste = "Tarif essai remise"
		manuel = frappe.get_doc("Item Price", {"price_list": liste, "item_code": self.autre})
		manuel.price_list_rate = 80
		manuel.save()
		source.price_list_rate = 1520
		source.save()
		autre.price_list_rate = 99
		autre.save()
		nouveau = _article("Essai tarif calculé ter")
		self._prix(nouveau, 200, self.today)
		changements = {row["article"]: row for row in T.get_changements(liste)["changements"]}
		self.assertEqual(set(changements), {self.article, self.autre, nouveau})
		self.assertEqual(
			(changements[self.article]["type"], changements[self.article]["nouveau"]), ("prix", 1368)
		)
		self.assertFalse(changements[self.article]["manuel"])
		self.assertTrue(changements[self.autre]["manuel"])
		self.assertEqual(changements[nouveau]["type"], "nouveau")
		self.assertEqual(T.get_prix(liste, "Essai tarif calculé")["tarif"]["regle"]["changements"], 3)

		reponse = T.recalculer(
			liste,
			[changements[self.article]["cle"], changements[nouveau]["cle"]],
			[changements[self.autre]["cle"]],
		)
		self.assertEqual(reponse["touches"], 3)
		self.assertEqual(reponse["changements"], [])
		self.assertEqual(self._taux(liste, self.article), {self.today: 1368})
		self.assertEqual(list(self._taux(liste, self.autre).values()), [80])
		self.assertEqual(list(self._taux(liste, nouveau).values()), [180])

		frappe.delete_doc("Item Price", source.name)
		changements = T.get_changements(liste)["changements"]
		self.assertEqual([(row["article"], row["type"]) for row in changements], [(self.article, "supprime")])
		T.recalculer(liste, [changements[0]["cle"]])
		self.assertEqual(self._taux(liste, self.article), {})

	def test_changer_la_regle_garde_les_prix_manuels(self):
		self._prix(self.article, 1000, add_days(self.today, -30))
		self._prix(self.autre, 500, add_days(self.today, -30))
		self._creer()
		liste = "Tarif essai remise"
		manuel = frappe.get_doc("Item Price", {"price_list": liste, "item_code": self.autre})
		manuel.price_list_rate = 400
		manuel.save()
		reponse = T.set_regle(liste, "remise", 20, 1)
		self.assertEqual(reponse["gardes"], 1)
		self.assertEqual(list(self._taux(liste, self.article).values()), [800])
		self.assertEqual(list(self._taux(liste, self.autre).values()), [400])
		self.assertEqual(calcul.regle(liste)["pourcentage"], 20)
		T.detacher(liste)
		self.assertIsNone(calcul.regle(liste))


class TestSuppressionTarif(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.base = _tarif("Tarif essai à supprimer", "vente")
		self.article = _article("Essai tarif suppression")
		self.today = nowdate()
		for debut, prix in ((add_days(self.today, -30), 100), (add_days(self.today, 30), 120)):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": self.base,
					"item_code": self.article,
					"uom": frappe.db.get_value("Item", self.article, "stock_uom"),
					"price_list_rate": prix,
					"valid_from": debut,
				}
			).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_supprimer_un_tarif_et_ses_prix(self):
		T.create_tarif("Tarif essai dérivé", "vente", base=self.base, ajustement="remise", pourcentage=10)
		reglages = T.delete_tarif(self.base)
		self.assertEqual((reglages["supprimes"], reglages["detaches"]), (2, ["Tarif essai dérivé"]))
		self.assertFalse(frappe.db.exists("Price List", self.base))
		self.assertFalse(frappe.db.exists("Item Price", {"price_list": self.base}))
		self.assertIsNone(calcul.regle("Tarif essai dérivé"))
		self.assertTrue(frappe.db.exists("Item Price", {"price_list": "Tarif essai dérivé"}))

	def test_le_tarif_par_defaut_ne_se_supprime_pas(self):
		T.set_tarif_defaut("vente", self.base)
		with self.assertRaises(frappe.ValidationError):
			T.delete_tarif(self.base)
		self.assertTrue(frappe.db.exists("Price List", self.base))

	def test_un_tarif_utilise_ne_se_supprime_pas(self):
		client = _tiers("Customer")
		if not client:
			self.skipTest("Aucun client sur ce site.")
		frappe.db.set_value("Customer", client, "default_price_list", self.base)
		with self.assertRaises(frappe.ValidationError) as refus:
			T.delete_tarif(self.base)
		self.assertIn("Désactivez-le", str(refus.exception))
		self.assertTrue(frappe.db.exists("Price List", self.base))
		self.assertEqual(frappe.db.count("Item Price", {"price_list": self.base}), 2)
