import { describe, expect, it } from 'vitest'
import LucideBox from '~icons/lucide/box'
import { filterPages, type GotoPage } from './goto'

const page = (id: string, label: string, module: string): GotoPage => ({ id, label, module, icon: LucideBox, to: { name: id } })
const pages = [page('accueil', 'Accueil', ''), page('factures', 'Factures', 'Ventes'), page('factures-achat', "Factures d'achat", 'Achats'), page('etat', 'État du stock', 'Stock'), page('lots', 'Lots', 'Stock')]
const ids = (query: string) => filterPages(pages, query).map((item) => item.id)

describe('aller à', () => {
	it('montre tout sans saisie, dans l’ordre du menu', () => {
		expect(ids('')).toEqual(['accueil', 'factures', 'factures-achat', 'etat', 'lots'])
	})

	it('cherche sans accents ni casse, dans le nom et le module', () => {
		expect(ids('etat')).toEqual(['etat'])
		expect(ids('STOCK')).toEqual(['etat', 'lots'])
		expect(ids('fact achat')).toEqual(['factures-achat'])
	})

	it('met devant les pages dont le nom commence par la saisie', () => {
		expect(ids('lo')).toEqual(['lots'])
		expect(ids('ach')).toEqual(['factures-achat'])
		expect(ids('zzz')).toEqual([])
	})
})
