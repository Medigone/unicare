import { afterEach, describe, expect, it } from 'vitest'
import { ecransLabels, estRaccourciAide, filtrerArticlesAide, lienArticle, rangerRubriques, sommaireUtile, surligner, titreCourt, type AideCarte } from './aide'

describe('liens des articles', () => {
	it('reconnaît un lien vers un article, avec son ancre', () => {
		expect(lienArticle('/bureau/aide/a/ventes-devis')).toEqual({ slug: 'ventes-devis', ancre: '' })
		expect(lienArticle('/bureau/aide/a/ventes-devis#comment-faire')).toEqual({ slug: 'ventes-devis', ancre: 'comment-faire' })
		expect(lienArticle(`${window.location.origin}/bureau/aide/a/stock-lots`)).toEqual({ slug: 'stock-lots', ancre: '' })
	})
	it('laisse les autres liens au navigateur', () => {
		expect(lienArticle('https://exemple.dz/bureau/aide/a/x')).toBeNull()
		expect(lienArticle('/bureau/devis')).toBeNull()
		expect(lienArticle('/bureau/aide/a/')).toBeNull()
		expect(lienArticle('')).toBeNull()
	})
})

describe('raccourci « ? »', () => {
	afterEach(() => {
		document.body.innerHTML = ''
	})
	const touche = (init: KeyboardEventInit, target?: Element) => {
		const event = new KeyboardEvent('keydown', { key: '?', ...init })
		if (target) Object.defineProperty(event, 'target', { value: target })
		return event
	}
	it('ouvre l’aide hors saisie', () => {
		expect(estRaccourciAide(touche({}, document.body))).toBe(true)
		expect(estRaccourciAide(new KeyboardEvent('keydown', { key: '/' }))).toBe(false)
	})
	it('se tait pendant une saisie, avec un modificateur ou sous une fenêtre', () => {
		const champ = document.createElement('input')
		expect(estRaccourciAide(touche({}, champ))).toBe(false)
		expect(estRaccourciAide(touche({ ctrlKey: true }, document.body))).toBe(false)
		document.body.innerHTML = '<div class="dialog-scrim"></div>'
		expect(estRaccourciAide(touche({}, document.body))).toBe(false)
	})
})

describe('sommaire et listes', () => {
	it('ne montre un sommaire qu’à partir de trois titres', () => {
		expect(sommaireUtile([{ id: 'a', titre: 'A' }, { id: 'b', titre: 'B' }])).toBe(false)
		expect(sommaireUtile([{ id: 'a', titre: 'A' }, { id: 'b', titre: 'B' }, { id: 'c', titre: 'C' }])).toBe(true)
		expect(sommaireUtile(undefined)).toBe(false)
	})
	it('filtre par statut et par mots, sans accents', () => {
		const articles = [
			{ titre: 'Faire un devis', resume: '', statut: 'Publié' as const, ecrans: ['devis'] },
			{ titre: 'Prévoir un changement de prix', resume: 'Les périodes', statut: 'Brouillon' as const, ecrans: ['tarifs'] },
		]
		expect(filtrerArticlesAide(articles, 'periode', 'tous').map((a) => a.titre)).toEqual(['Prévoir un changement de prix'])
		expect(filtrerArticlesAide(articles, '', 'Publié').map((a) => a.titre)).toEqual(['Faire un devis'])
		expect(filtrerArticlesAide(articles, 'devis faire', 'tous')).toHaveLength(1)
		expect(filtrerArticlesAide(articles, 'tarifs', 'Publié')).toHaveLength(0)
	})
	it('nomme les écrans par leur libellé du menu', () => {
		expect(ecransLabels(['devis', 'inconnu'], [{ id: 'devis', label: 'Ventes · Devis' }])).toEqual(['Ventes · Devis', 'inconnu'])
	})
})

describe('accueil du centre d\'aide', () => {
	const carte = (slug: string, titre: string): AideCarte => ({ slug, titre, categorie: slug.split('-')[0], resume: '', duree_lecture: 1 })
	it('raccourcit les titres qui répètent la rubrique', () => {
		expect(titreCourt('Réglages : Ventes', 'Réglages')).toBe('Ventes')
		expect(titreCourt('Faire un devis', 'Ventes')).toBe('Faire un devis')
	})
	it('range les rubriques en quotidien et réglages, vue d\'ensemble et messages à part', () => {
		const { quotidien, reglages } = rangerRubriques([
			{ slug: 'ventes', titre: 'Ventes', description: '', icone: '', articles: [carte('ventes-vue-d-ensemble', "Ventes : vue d'ensemble"), carte('ventes-devis', 'Faire un devis'), carte('ventes-messages', 'Ventes : messages et raccourcis')] },
			{ slug: 'reglages', titre: 'Réglages', description: '', icone: '', articles: [carte('reglages-ventes', 'Réglages : Ventes')] },
		])
		expect(quotidien.map((r) => r.slug)).toEqual(['ventes'])
		expect(quotidien[0].vueEnsemble?.slug).toBe('ventes-vue-d-ensemble')
		expect(quotidien[0].messages?.slug).toBe('ventes-messages')
		expect(quotidien[0].etapes.map((a) => a.slug)).toEqual(['ventes-devis'])
		expect(reglages[0].etapes[0].titre).toBe('Ventes')
		expect(reglages[0].vueEnsemble).toBeNull()
	})
})

describe('surligner', () => {
	it('marque les mots cherchés sans tenir compte des accents ni des majuscules', () => {
		expect(surligner('Créer un avoir. Échéance', 'avoir echeance')).toEqual([
			{ texte: 'Créer un ', trouve: false },
			{ texte: 'avoir', trouve: true },
			{ texte: '. ', trouve: false },
			{ texte: 'Échéance', trouve: true },
		])
	})
	it('laisse le texte entier sans mot à chercher', () => {
		expect(surligner('Texte', 'x')).toEqual([{ texte: 'Texte', trouve: false }])
		expect(surligner('', 'avoir')).toEqual([])
	})
})
