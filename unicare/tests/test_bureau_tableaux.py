# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from unicare.api import bureau_achats, bureau_tableaux
from unicare.api import bureau_commandes_achat as CA
from unicare.api import bureau_factures_achat as FA
from unicare.tests.achats_outils import article, fournisseur


class TestPeriodes(FrappeTestCase):
	def test_bornes_et_periode_precedente(self):
		mois = bureau_tableaux.periode("mois", "2026-11-11")
		self.assertEqual((str(mois["debut"]), str(mois["fin"])), ("2026-11-01", "2026-11-11"))
		self.assertEqual((str(mois["avant_debut"]), str(mois["avant_fin"])), ("2026-10-01", "2026-10-11"))
		self.assertEqual(mois["avant"], "octobre")
		# Fin de mois plus longue que le mois d'avant : la comparaison s'arrête à sa fin.
		mars = bureau_tableaux.periode("mois", "2026-03-31")
		self.assertEqual(str(mars["avant_fin"]), "2026-02-28")
		trente = bureau_tableaux.periode("30j", "2026-11-11")
		self.assertEqual((str(trente["debut"]), str(trente["avant_fin"])), ("2026-10-13", "2026-10-12"))
		trimestre = bureau_tableaux.periode("trimestre", "2026-11-11")
		self.assertEqual((str(trimestre["debut"]), trimestre["libelle"], trimestre["avant"]), ("2026-10-01", "T4 2026", "T3"))
		self.assertEqual(bureau_tableaux.periode("trimestre", "2026-02-01")["avant"], "T4")
		annee = bureau_tableaux.periode("annee", "2026-11-11")
		self.assertEqual((str(annee["debut"]), str(annee["avant_debut"]), str(annee["avant_fin"])), ("2026-01-01", "2025-01-01", "2025-11-11"))

	def test_mois_et_semaines_du_graphique(self):
		mois = bureau_tableaux._months(getdate("2026-11-11"))
		self.assertEqual((len(mois), mois[0][0], mois[-1][0], mois[-1][1]), (12, "2025-12", "2026-11", "nov."))
		semaines = bureau_tableaux._weeks(getdate("2026-11-11"))
		self.assertEqual((len(semaines), str(semaines[-1][0]), semaines[-1][1]), (8, "2026-11-09", "9 nov."))

	def test_badges_d_echeance(self):
		self.assertEqual(bureau_tableaux._jours(add_days(today(), -3)), {"texte": "en retard de 3 j", "ton": "red"})
		self.assertEqual(bureau_tableaux._jours(today())["texte"], "aujourd'hui")
		self.assertEqual(bureau_tableaux._jours(add_days(today(), 1))["texte"], "demain")
		self.assertEqual(bureau_tableaux._jours(add_days(today(), 5)), {"texte": "dans 5 j", "ton": "gray"})
		self.assertEqual(bureau_tableaux._echue(add_days(today(), -6))["texte"], "échue de 6 j")


class TestTableaux(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.lang = "fr"

	def tearDown(self):
		frappe.db.rollback()

	def test_chaque_module_suit_le_meme_gabarit(self):
		for module in bureau_tableaux.MODULES:
			tableau = bureau_tableaux.get_tableau(module, "annee")
			self.assertEqual(tableau["module"], module)
			self.assertEqual(len(tableau["indicateurs"]), 4, module)
			self.assertEqual(len(tableau["listes"]), 4, module)
			self.assertTrue(tableau["tendance"], module)
			for indicateur in tableau["indicateurs"]:
				self.assertTrue(indicateur["lien"]["page"])
			for liste in tableau["listes"]:
				self.assertLessEqual(len(liste["lignes"]), bureau_tableaux.LIMITE)
				self.assertGreaterEqual(liste["total"], len(liste["lignes"]))
		self.assertTrue(bureau_tableaux.get_tableau("stock")["sans_periode"])
		self.assertTrue(bureau_tableaux.get_tableau("tresorerie")["echeancier"])
		with self.assertRaises(frappe.ValidationError):
			bureau_tableaux.get_tableau("inconnu")
		# Une période inconnue retombe sur le mois.
		self.assertEqual(bureau_tableaux.get_tableau("ventes", "siecle")["periode"]["key"], "mois")

	def test_une_facture_d_achat_entre_dans_achats_et_tresorerie(self):
		achats = {k["key"]: k["valeur"] for k in bureau_tableaux.get_tableau("achats")["indicateurs"]}
		tresorerie = {k["key"]: k["valeur"] for k in bureau_tableaux.get_tableau("tresorerie")["indicateurs"]}
		nom = fournisseur("Fournisseur Essai Tableaux")
		code = article("Service essai tableau", 1000)
		commande = CA.create_commande_achat(
			json.dumps(
				{
					"fournisseur": nom,
					"reception": add_days(today(), 3),
					"taxes": bureau_achats.taxes_options(CA._company())["taxes_defaut"],
					"lignes": [{"article": code, "quantite": 2}],
				}
			)
		)["name"]
		fiche = CA.validate_commande_achat(commande, CA.get_commande_achat(commande)["modified"])
		facture = CA.create_suivante(commande, fiche["modified"], "facture")["name"]
		fiche = FA.update_facture_achat(
			facture,
			FA.get_facture_achat(facture)["modified"],
			json.dumps({"numero_fournisseur": "FF-TDB-1", "date_fournisseur": today(), "echeance": add_days(today(), 2)}),
		)
		fiche = FA.validate_facture_achat(facture, fiche["modified"])

		tableau = bureau_tableaux.get_tableau("achats")
		apres = {k["key"]: k["valeur"] for k in tableau["indicateurs"]}
		self.assertAlmostEqual(apres["achats"] - achats["achats"], 2000, places=2)
		self.assertAlmostEqual(apres["reste"] - achats["reste"], fiche["total_ttc"], places=2)
		a_payer = next(liste for liste in tableau["listes"] if liste["key"] == "factures_a_payer")
		ligne = next(ligne for ligne in a_payer["lignes"] if ligne["name"] == facture)
		self.assertEqual((ligne["fiche"], ligne["badge"]["texte"], ligne["detail"]), ("FactureAchatFiche", "dans 2 j", frappe.db.get_value("Supplier", nom, "supplier_name")))
		self.assertEqual(a_payer["lien"], {"page": "FacturesAchat", "vue": "a_payer"})
		fournisseurs = [ligne["name"] for ligne in tableau["repartition"]["lignes"]]
		self.assertIn(nom, fournisseurs)

		apres = {k["key"]: k["valeur"] for k in bureau_tableaux.get_tableau("tresorerie")["indicateurs"]}
		self.assertAlmostEqual(apres["payer"] - tresorerie["payer"], fiche["total_ttc"], places=2)

		# Payée : sort de « à payer » et entre dans le décaissé du mois.
		FA.payer(facture, fiche["modified"], fiche["total_ttc"], "Espèces")
		tableau = bureau_tableaux.get_tableau("tresorerie")
		final = {k["key"]: k["valeur"] for k in tableau["indicateurs"]}
		self.assertAlmostEqual(final["payer"], tresorerie["payer"], places=2)
		self.assertAlmostEqual(final["decaisse"] - tresorerie["decaisse"], fiche["total_ttc"], places=2)
		semaine = tableau["tendance"]["points"][-1]["valeurs"][1]
		self.assertGreaterEqual(semaine, fiche["total_ttc"])
