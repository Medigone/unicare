"""Contexte éditorial de la landing page publique Unicare.

Les contenus temporaires sont centralisés ici afin de pouvoir être remplacés
sans modifier la structure HTML de la page.
"""

no_cache = 1


def get_context(context):
	context.no_breadcrumbs = True
	context.full_width = True
	context.title = "Unicare — Soins doux pour la peau de bébé"
	context.description = (
		"Découvrez une gamme de soins pour bébés conçue pour nettoyer, hydrater "
		"et protéger les peaux délicates avec douceur et transparence."
	)
	context.brand = {
		"name": "Unicare",
		"tagline": "Les essentiels doux de bébé",
		"email": "contact@unicare.example",
		"phone": "+213 (0) 00 00 00 00",
		"address": "Adresse à compléter, Algérie",
	}
	context.links = {
		"products": "#produits",
		"formulas": "#ingredients",
		"instagram": "#",
		"facebook": "#",
		"linkedin": "#",
		"legal": "#",
		"privacy": "#",
		"terms": "#",
	}
	context.images = {
		"hero": "/assets/unicare/images/baby-care/composition_produits_hero.png?v=1",
		"products": "/assets/unicare/images/baby-care/product-care.svg?v=2",
		"family": "/assets/unicare/images/baby-care/parent_baby.png?v=1",
		"ingredient": "/assets/unicare/images/baby-care/ingredients.png?v=1",
		"quality": "/assets/unicare/images/baby-care/laboratoire.png?v=1",
		"advice": "/assets/unicare/images/baby-care/advice.svg?v=2",
	}
	context.nav_items = [
		{"label": "Nos produits", "href": "#produits"},
		{"label": "Nos engagements", "href": "#engagements"},
		{"label": "Nos ingrédients", "href": "#ingredients"},
		{"label": "Notre qualité", "href": "#qualite"},
		{"label": "Conseils", "href": "#conseils"},
	]
	context.reassurances = [
		"Formules adaptées aux peaux sensibles",
		"Contrôles qualité rigoureux",
		"Ingrédients soigneusement sélectionnés",
	]
	context.commitments = [
		{"icon": "drop", "title": "Douceur quotidienne", "text": "Des textures pensées pour les gestes de chaque jour."},
		{"icon": "heart", "title": "Peaux sensibles", "text": "Des formules conçues avec attention pour les peaux délicates."},
		{"icon": "shield", "title": "Fabrication maîtrisée", "text": "Un suivi attentif, de la formule au produit fini."},
		{"icon": "leaf", "title": "Formules transparentes", "text": "Des ingrédients présentés de façon claire et accessible."},
	]
	context.products = [
		{
			"category": "Bain et toilette",
			"name": "Gel lavant douceur",
			"description": "Nettoie délicatement la peau et les cheveux lors du bain.",
			"image": context.images["products"],
			"tone": "sand",
		},
		{
			"category": "Hydratation",
			"name": "Lait corps confort",
			"description": "Aide à préserver la souplesse et le confort de la peau.",
			"image": context.images["products"],
			"tone": "sage",
		},
		{
			"category": "Change",
			"name": "Crème de change",
			"description": "Forme un film protecteur doux sur la zone du siège.",
			"image": context.images["products"],
			"tone": "rose",
		},
		{
			"category": "Cheveux",
			"name": "Shampooing délicat",
			"description": "Lave les cheveux fins sans alourdir ni dessécher.",
			"image": context.images["products"],
			"tone": "cream",
		},
		{
			"category": "Protection quotidienne",
			"name": "Baume multi-usages",
			"description": "Nourrit les zones sèches et apporte un confort ciblé.",
			"image": context.images["products"],
			"tone": "clay",
		},
	]
	context.skin_principles = [
		{"number": "01", "title": "Nettoyer sans agresser", "text": "Privilégier des gestes courts, une eau tiède et une formule lavante douce."},
		{"number": "02", "title": "Hydrater en douceur", "text": "Appliquer un soin adapté sur une peau propre, sans frotter."},
		{"number": "03", "title": "Protéger au quotidien", "text": "Observer la peau et adapter la routine aux besoins du moment."},
	]
	context.ingredients = [
		{"name": "Calendula", "function": "Contribue à apaiser et adoucir la peau.", "initial": "Ca"},
		{"name": "Glycérine", "function": "Aide à maintenir l’hydratation de la peau.", "initial": "Gl"},
		{"name": "Huile d’amande douce", "function": "Nourrit et assouplit la peau.", "initial": "Am"},
		{"name": "Aloe vera", "function": "Apporte confort et fraîcheur à l’application.", "initial": "Av"},
	]
	context.quality_steps = [
		{"number": "01", "title": "Sélection des matières premières", "text": "Choix selon des critères définis de qualité et de traçabilité."},
		{"number": "02", "title": "Formulation", "text": "Développement de formules simples, adaptées à l’usage prévu."},
		{"number": "03", "title": "Contrôle qualité", "text": "Vérifications selon les procédures applicables à chaque lot."},
		{"number": "04", "title": "Conditionnement", "text": "Mise en contenant et identification pour assurer le suivi du produit."},
	]
	context.stats = [
		{"value": "XX", "label": "années d’expérience"},
		{"value": "XX", "label": "références"},
		{"value": "XX", "label": "points de vente"},
		{"value": "Locale", "label": "production"},
	]
	context.advice = [
		{"title": "Le bain de bébé", "summary": "Température, durée et gestes : les repères pour un moment serein.", "tag": "Routine bain"},
		{"title": "Hydrater après la toilette", "summary": "Quelques gestes simples pour appliquer le soin avec douceur.", "tag": "Hydratation"},
		{"title": "Prendre soin de la zone du change", "summary": "Nettoyer, sécher et protéger sans multiplier les produits.", "tag": "Change"},
	]
	context.testimonials = [
		{"quote": "La texture est légère, le produit s’applique facilement et son parfum reste très discret.", "name": "Sarah", "role": "Maman de Lina"},
		{"quote": "J’apprécie les explications claires sur la formule et la routine reste vraiment simple.", "name": "Nadia", "role": "Parent utilisateur"},
		{"quote": "Le flacon est pratique au quotidien et le lait pénètre rapidement sans effet collant.", "name": "Amel", "role": "Maman de Yacine"},
	]
	context.faqs = [
		{"question": "À partir de quel âge peut-on utiliser les produits ?", "answer": "L’âge d’utilisation dépend de chaque référence. Consultez toujours l’étiquette et les précautions du produit avant la première utilisation."},
		{"question": "Les produits conviennent-ils aux peaux sensibles ?", "answer": "La gamme est développée avec les peaux délicates en tête. La composition et les indications propres à chaque produit restent disponibles sur sa fiche et son emballage."},
		{"question": "Où sont fabriqués les produits ?", "answer": "Les informations exactes de fabrication seront indiquées ici dès leur validation. Elles figurent également sur l’emballage de chaque produit."},
		{"question": "Comment consulter la liste des ingrédients ?", "answer": "La liste INCI complète figure sur chaque emballage. Une version en ligne sera ajoutée aux fiches produits pour faciliter sa consultation."},
		{"question": "Où peut-on acheter la gamme ?", "answer": "La liste des pharmacies et revendeurs partenaires sera prochainement disponible dans notre outil de recherche de points de vente."},
		{"question": "Comment conserver les produits après ouverture ?", "answer": "Conservez-les selon les indications de l’emballage, à l’abri d’une chaleur excessive, et respectez la durée d’utilisation après ouverture."},
	]
	return context
