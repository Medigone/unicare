import { afterEach, describe, expect, it } from 'vitest'
import LucideBox from '~icons/lucide/box'
import { activePoste, availablePostes, moduleOf, moduleTarget, NAV, navFor, pagesFor, setPoste } from './postes'

const modules = (key: string) => navFor(key).map((module) => module.id)
const pages = (key: string, module: string) => navFor(key).find((item) => item.id === module)?.groups.flatMap((group) => group.items.map((item) => item.id)) ?? []
const noRead = (...doctypes: string[]) => Object.fromEntries(doctypes.map((doctype) => [doctype, { read: false, create: false }]))

afterEach(() => {
	delete window.postes
	delete window.droits
	localStorage.clear()
	setPoste('')
})

describe('postes du bureau', () => {
	it('ouvre le poste Conditionnement sans liste du serveur', () => {
		expect(availablePostes().map((poste) => poste.key)).toEqual(['conditionnement'])
		expect(activePoste().label).toBe('Conditionnement')
	})

	it('range le menu par module, Accueil en tête', () => {
		expect(modules('conditionnement')).toEqual(['accueil', 'ventes', 'achats', 'stock', 'tresorerie', 'production'])
		expect(pages('conditionnement', 'ventes')).toEqual(['tableau-ventes', 'devis', 'commandes', 'livraisons', 'factures', 'clients'])
		expect(pages('conditionnement', 'achats')).toEqual(['tableau-achats', 'devis-fournisseurs', 'commandes-achat', 'receptions', 'factures-achat', 'fournisseurs'])
		expect(pages('conditionnement', 'stock')).toEqual(['tableau-stock', 'etat-stock', 'mouvements', 'inventaires', 'lots', 'articles', 'depots'])
		expect(pages('conditionnement', 'tresorerie')).toEqual(['tableau-tresorerie', 'paiements'])
		expect(pages('conditionnement', 'production')).toEqual(['tableau-production', 'ordres', 'recettes', 'reglages-production'])
	})

	it('retire une page non lue, puis le module resté vide', () => {
		window.droits = noRead('Customer')
		expect(pages('conditionnement', 'ventes')).not.toContain('clients')
		window.droits = noRead('Payment Entry')
		expect(modules('conditionnement')).not.toContain('tresorerie')
		window.droits = noRead('Ordre de Conditionnement', 'Recette de Conditionnement', 'Checklist Ordre Conditionnement')
		expect(modules('conditionnement')).not.toContain('production')
	})

	it('ouvre le module de la page affichée, et mène à sa première page', () => {
		const list = navFor('conditionnement')
		expect(moduleOf(list, 'factures-achat')?.id).toBe('achats')
		expect(moduleOf(list, 'accueil')?.id).toBe('accueil')
		expect(moduleOf(list, 'inconnue')?.id).toBe('accueil')
		expect(moduleTarget(list.find((module) => module.id === 'stock')!)).toEqual({ to: { name: 'TableauStock' }, href: undefined })
		expect(moduleOf(list, 'tableau-ventes')?.id).toBe('ventes')
		expect(moduleTarget(list.find((module) => module.id === 'accueil')!)).toEqual({ to: { name: 'Home' } })
		expect(moduleTarget(list.find((module) => module.id === 'production')!).to).toEqual({ name: 'TableauProduction' })
	})

	it('liste toutes les pages, avec leur module, pour « Aller à… »', () => {
		const all = pagesFor('conditionnement')
		expect(all[0]).toMatchObject({ id: 'accueil', module: '' })
		expect(all.find((page) => page.id === 'lots')).toMatchObject({ label: 'Lots', module: 'Stock' })
		expect(all.find((page) => page.id === 'tableau-achats')).toMatchObject({ label: 'Tableau de bord', module: 'Achats' })
	})

	it("retient le choix et ignore un poste qui n'est plus à ce compte", () => {
		window.postes = [
			{ key: 'conditionnement', label: 'Conditionnement' },
			{ key: 'autre', label: 'Autre' },
		]
		setPoste('autre')
		expect(activePoste().key).toBe('autre')
		window.postes = [{ key: 'conditionnement', label: 'Conditionnement' }]
		expect(activePoste().key).toBe('conditionnement')
	})

	it('garde un module qui est une page même sans sous-pages', () => {
		NAV.essai = [
			{ id: 'accueil', label: 'Accueil', icon: LucideBox, to: { name: 'Home' }, groups: [] },
			{ id: 'vide', label: 'Vide', icon: LucideBox, groups: [{ title: 'Rien', items: [{ id: 'x', label: 'X', icon: LucideBox, href: '/app/x', doctype: 'Ordre de Conditionnement' }] }] },
		]
		try {
			window.droits = noRead('Ordre de Conditionnement')
			expect(modules('essai')).toEqual(['accueil'])
		} finally {
			delete NAV.essai
		}
	})

	it("n'a pas de menu pour un poste inconnu", () => {
		expect(navFor('inconnu')).toEqual([])
	})
})
