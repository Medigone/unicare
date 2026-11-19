# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.aide import import_guides, rendu
from unicare.aide.index import vider_cache
from unicare.api import bureau_aide as A

LECTEUR = "lecteur.aide@example.com"


def _lecteur():
	if not frappe.db.exists("User", LECTEUR):
		user = frappe.get_doc(
			{"doctype": "User", "email": LECTEUR, "first_name": "Lecteur", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles("Opérateur Conditionnement")
	return LECTEUR


class TestRendu(FrappeTestCase):
	def test_conventions(self):
		html, minutes = rendu.rendre(
			"## Faire un devis\n\nCliquez sur :btn[Valider] puis :alt[Modifier] dans :chemin[Ventes > Devis], "
			"champ :champ[Client], statut :pastille-vert[Payée], touche <kbd>N</kbd>.\n\n> [!attention] Vérifiez."
		)
		self.assertIn('<h2 id="faire-un-devis">', html)
		self.assertIn('<span class="aide-btn">Valider</span>', html)
		self.assertIn('<span class="aide-btn aide-btn-alt">Modifier</span>', html)
		self.assertIn('<span class="aide-chemin">Ventes<i aria-hidden="true">›</i>Devis</span>', html)  # noqa: RUF001
		self.assertIn('<span class="aide-champ">Client</span>', html)
		self.assertIn('<span class="aide-pastille aide-pastille-vert">Payée</span>', html)
		self.assertIn("<kbd>N</kbd>", html)
		self.assertIn('<aside class="aide-encadre aide-encadre-attention">', html)
		self.assertEqual(minutes, 1)

	def test_html_dangereux_retire(self):
		html, _m = rendu.rendre(
			"<script>alert(1)</script><img src=x onerror=alert(2)>"
			"[lien](javascript:alert(3)) <a href='/x' onclick='y'>z</a> :btn[<b>x</b>]"
		)
		for interdit in ("<script", "onerror", "javascript:", "onclick", 'class="aide-btn"'):
			self.assertNotIn(interdit, html)

	def test_texte_brut(self):
		self.assertEqual(
			rendu.texte_brut("Elle **réserve le stock**, le :champ[Reste dû] et [la facture](/x) `code`."),
			"Elle réserve le stock, le Reste dû et la facture code.",
		)

	def test_sommaire_et_ecrans(self):
		html, _m = rendu.rendre("## Un\n\ntexte\n\n## Un\n\nencore")
		self.assertEqual([s["id"] for s in rendu.sommaire(html)], ["un", "un-2"])
		self.assertEqual(
			rendu.nettoyer_ecrans("devis, Factures\ndevis <x> tableau-ventes"),
			"devis\nfactures\ntableau-ventes",
		)


class TestAide(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		import_guides.importer()
		vider_cache()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		vider_cache()

	def test_import_des_guides(self):
		devis = frappe.get_doc("Article Aide", "ventes-devis")
		self.assertEqual(devis.titre, "Faire un devis")
		self.assertEqual(devis.categorie, "ventes")
		self.assertEqual(devis.statut, "Publié")
		self.assertIn("devis", devis.ecrans.split())
		self.assertIn('class="aide-btn"', devis.contenu_html)
		self.assertTrue(frappe.db.exists("Article Aide", "ventes-vue-d-ensemble"))
		self.assertTrue(frappe.db.exists("Article Aide", "ventes-messages"))
		self.assertIn(
			"tableau-ventes", frappe.db.get_value("Article Aide", "ventes-vue-d-ensemble", "ecrans").split()
		)

	def test_reimport_sans_doublon_et_respecte_les_retouches(self):
		avant = frappe.db.count("Article Aide")
		doc = frappe.get_doc("Article Aide", "ventes-devis")
		doc.contenu_markdown += "\n\nUne précision ajoutée à la main.\n"
		doc.save()
		bilan = import_guides.importer()
		self.assertEqual(frappe.db.count("Article Aide"), avant)
		self.assertEqual(bilan["crees"], [])
		self.assertIn("ventes-devis", bilan["inchanges"])  # le guide n'a pas changé : rien à reprendre
		# le guide change (empreinte différente) : l'article retouché reste tel quel
		frappe.db.set_value("Article Aide", "ventes-devis", "empreinte_source", "guide-modifie")
		bilan = import_guides.importer()
		self.assertIn("ventes-devis", bilan["gardes"])
		self.assertIn(
			"précision ajoutée", frappe.db.get_value("Article Aide", "ventes-devis", "contenu_markdown")
		)

	def test_reimport_met_a_jour_un_article_non_retouche(self):
		frappe.db.set_value("Article Aide", "ventes-client", "empreinte_source", "ancienne")
		frappe.db.set_value("Article Aide", "ventes-client", "contenu_markdown", "vieux")
		bilan = import_guides.importer()
		self.assertNotIn(
			"ventes-client", bilan["mis_a_jour"]
		)  # « vieux » ne correspond pas à l'empreinte : retouché
		frappe.db.set_value("Article Aide", "ventes-client", "empreinte_source", None)
		bilan = import_guides.importer()
		self.assertIn("ventes-client", bilan["mis_a_jour"])
		self.assertIn(
			"Raison sociale", frappe.db.get_value("Article Aide", "ventes-client", "contenu_markdown")
		)

	def test_recherche_sans_accents_et_sur_cette_page(self):
		resultat = A.rechercher("echeance avoir", "factures")
		tous = [a["slug"] for a in resultat["page"] + resultat["autres"]]
		self.assertTrue(tous)
		self.assertTrue(all(a["slug"] for a in resultat["page"]))
		resultat = A.rechercher("prevoir changement", None)
		self.assertIn("tarifs-periodes", [a["slug"] for a in resultat["autres"]])
		self.assertEqual(A.rechercher("x", None), {"page": [], "autres": []})

		# « avoir » est aussi un verbe : seuls les articles où c'est un nom (« un avoir ») sortent
		avoir = A.rechercher("avoir", None)["autres"]
		self.assertIn("ventes-facture", [a["slug"] for a in avoir])
		self.assertLess(len(avoir), 5)
		self.assertIn("avoir", avoir[0]["extrait"].lower())

		inventaire = A.rechercher("inventaire", None)["autres"]
		self.assertEqual(inventaire[0]["slug"], "stock-inventaire")
		self.assertTrue(inventaire[0]["sommaire"])
		self.assertNotIn("sommaire", inventaire[1])
		self.assertNotIn("**", "".join(a["resume"] for a in A.get_accueil()["categories"][0]["articles"]))

		accueil = A.get_accueil("devis")
		self.assertIn("ventes-devis", [a["slug"] for a in accueil["sur_cette_page"]])
		self.assertIn("ventes", [c["slug"] for c in accueil["categories"]])

	def test_article_et_voisins(self):
		article = A.get_article("ventes-devis")
		self.assertEqual(article["categorie"]["slug"], "ventes")
		self.assertEqual(article["precedent"]["slug"], "ventes-client")
		self.assertEqual(article["suivant"]["slug"], "ventes-commande")
		self.assertIn("comment-faire", [s["id"] for s in article["sommaire"]])

	def test_brouillon_invisible(self):
		frappe.db.set_value("Article Aide", "ventes-devis", "statut", "Brouillon")
		vider_cache()
		self.assertNotIn("ventes-devis", [a["slug"] for a in A.get_accueil("devis")["sur_cette_page"]])
		frappe.set_user(_lecteur())
		with self.assertRaises(frappe.DoesNotExistError):
			A.get_article("ventes-devis")
		self.assertNotIn("ventes-devis", [a["slug"] for a in A.rechercher("devis", None)["autres"]])

	def test_edition_refusee_sans_droit(self):
		frappe.set_user(_lecteur())
		self.assertFalse(A.get_article("ventes-devis")["peut_editer"])
		with self.assertRaises(frappe.PermissionError):
			A.list_articles()
		with self.assertRaises(frappe.PermissionError):
			A.save_article("ventes-devis", "x", {"titre": "Piraté"})

	def test_edition_et_garde(self):
		edition = A.get_article_edition("ventes-devis")
		apres = A.save_article(
			"ventes-devis",
			edition["modified"],
			{
				"titre": "Faire un devis client",
				"ecrans": ["devis", "clients", "DEVIS"],
				"contenu_markdown": "## Étapes\n\n:btn[Go]",
			},
		)
		self.assertEqual(apres["titre"], "Faire un devis client")
		self.assertEqual(apres["ecrans"], ["devis", "clients"])
		self.assertIn('<h2 id="etapes">', apres["html"])
		self.assertEqual(A.get_article("ventes-devis")["titre"], "Faire un devis client")  # le cache est vidé
		with self.assertRaises(frappe.TimestampMismatchError):
			A.save_article("ventes-devis", edition["modified"], {"titre": "Encore"})

	def test_creer_et_supprimer(self):
		cree = A.create_article(
			{"titre": "Faire un devis", "categorie": "ventes", "contenu_markdown": "Texte"}
		)
		self.assertEqual(cree["slug"], "faire-un-devis")
		self.assertEqual(cree["statut"], "Brouillon")
		self.assertGreater(cree["ordre"], 10)
		self.assertEqual(
			A.apercu(":champ[Client]")["html"], '<p><span class="aide-champ">Client</span></p>\n'
		)
		A.delete_article(cree["slug"], cree["modified"])
		self.assertFalse(frappe.db.exists("Article Aide", cree["slug"]))
