import { afterEach, describe, expect, it } from 'vitest'
import LucideBox from '~icons/lucide/box'
import { activePoste, availablePostes, NAV, navFor, setPoste } from './postes'

const ids = (key: string) => navFor(key).flatMap((group) => group.items.map((item) => item.id))
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

	it("commence par l'accueil, puis le référentiel", () => {
		expect(ids('conditionnement')).toEqual(['accueil', 'devis', 'commandes', 'livraisons', 'factures', 'paiements', 'clients', 'articles'])
	})

	it('retire Clients à qui ne lit pas les clients', () => {
		window.droits = noRead('Customer')
		expect(ids('conditionnement')).toEqual(['accueil', 'devis', 'commandes', 'livraisons', 'factures', 'paiements', 'articles'])
	})

	it('retire Articles à qui ne lit pas les articles', () => {
		window.droits = noRead('Item')
		expect(ids('conditionnement')).toEqual(['accueil', 'devis', 'commandes', 'livraisons', 'factures', 'paiements', 'clients'])
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

	it('retire une entrée non lue et le groupe resté vide', () => {
		NAV.essai = [
			{ title: 'Mon travail', items: [{ id: 'accueil', label: 'Accueil', icon: LucideBox, to: { name: 'Home' } }] },
			{ title: 'Production', items: [{ id: 'ordres', label: 'Ordres', icon: LucideBox, href: '/app/ordre-de-conditionnement', doctype: 'Ordre de Conditionnement' }] },
		]
		try {
			expect(navFor('essai').map((group) => group.title)).toEqual(['Mon travail', 'Production'])
			window.droits = noRead('Ordre de Conditionnement')
			expect(navFor('essai').map((group) => group.title)).toEqual(['Mon travail'])
		} finally {
			delete NAV.essai
		}
	})

	it("n'a pas de menu pour un poste inconnu", () => {
		expect(navFor('inconnu')).toEqual([])
	})
})
