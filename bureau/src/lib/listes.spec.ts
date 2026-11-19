import { describe, expect, it } from 'vitest'
import { chemin, construireArbre, detailLabel, dossiersPossibles, filtrerValeurs, lienFiches, usagesLabel, type ListeValeur } from './listes'

const v = (name: string, actif = true): ListeValeur => ({ name, modified: '', usages: 0, actif })

describe('listes', () => {
	it('filtre sans accents ni casse, et les unités actives', () => {
		const valeurs = [v('Matières Premières'), v('Électrique'), v('Box', false)]
		expect(filtrerValeurs(valeurs, 'matieres').map((r) => r.name)).toEqual(['Matières Premières'])
		expect(filtrerValeurs(valeurs, 'ELEC').map((r) => r.name)).toEqual(['Électrique'])
		expect(filtrerValeurs(valeurs, '', 'actives')).toHaveLength(2)
		expect(filtrerValeurs(valeurs, '', 'toutes')).toHaveLength(3)
	})

	it('dit combien de fiches utilisent la valeur', () => {
		expect(usagesLabel(0)).toBe('Inutilisée')
		expect(usagesLabel(1)).toBe('1 fiche')
		expect(usagesLabel(4)).toBe('4 fiches')
	})

	it('nomme les fiches et détaille les usages', () => {
		expect(usagesLabel(142, 'clients')).toBe('142 clients')
		expect(usagesLabel(1, 'clients')).toBe('1 client')
		expect(usagesLabel(1, 'devis')).toBe('1 devis')
		expect(detailLabel({ articles: 64, prix: 120, 'lignes de recette': 18 })).toBe('64 articles · 120 prix · 18 lignes de recette')
		expect(detailLabel({ articles: 1, 'lignes de recette': 1, conversions: 0 })).toBe('1 article · 1 ligne de recette')
	})

	it('filtre par usage', () => {
		const valeurs = [{ ...v('A'), usages: 3 }, v('B'), v('C', false)]
		expect(filtrerValeurs(valeurs, '', 'utilisees').map((r) => r.name)).toEqual(['A'])
		expect(filtrerValeurs(valeurs, '', 'inutilisees').map((r) => r.name)).toEqual(['B', 'C'])
		expect(filtrerValeurs(valeurs, '', 'retirees').map((r) => r.name)).toEqual(['C'])
	})

	it('relie une valeur à ses fiches', () => {
		const lien = { page: 'Clients', doctype: 'Customer', champ: 'customer_group', fiches: 'clients' }
		expect(lienFiches({ lien }, 'Pharmacie')).toEqual({ name: 'Clients', query: { filtres: '[["Customer","customer_group","=","Pharmacie"]]' } })
	})

	describe('arbre', () => {
		const n = (name: string, parent: string | null, dossier = false, usages = 0): ListeValeur => ({ name, modified: '', usages, actif: true, dossier, parent })
		const valeurs = [n('Emballages', null, true), n('Flacons', 'Emballages', false, 14), n('Étiquettes', 'Emballages', false, 22), n('Verre', 'Emballages', true), n('Fioles', 'Verre', false, 0), n('Services', null, false, 2), n('Vide', null, true)]

		it('range dossiers puis valeurs, et compte le contenu', () => {
			const lignes = construireArbre(valeurs, { Emballages: true })
			expect(lignes.map((l) => [l.valeur.name, l.niveau])).toEqual([['Emballages', 1], ['Verre', 2], ['Étiquettes', 2], ['Flacons', 2], ['Vide', 1], ['Services', 1]])
			expect(lignes[0]).toMatchObject({ contenu: 3, enfants: 3, usagesTotal: 36, ouvert: true })
			expect(lignes[1]).toMatchObject({ ouvert: false, contenu: 1 })
		})

		it('ouvre les dossiers qui contiennent la recherche', () => {
			expect(construireArbre(valeurs, {}, 'fiole').map((l) => l.valeur.name)).toEqual(['Emballages', 'Verre', 'Fioles'])
			expect(construireArbre(valeurs, {}, '', 'inutilisees').map((l) => l.valeur.name)).toEqual(['Emballages', 'Verre', 'Fioles'])
		})

		it('propose les dossiers de destination sans boucle', () => {
			expect(dossiersPossibles(valeurs, valeurs[0]).map((d) => d.name)).toEqual(['Vide'])
			expect(dossiersPossibles(valeurs, valeurs[1])).toEqual([{ name: 'Emballages', niveau: 1 }, { name: 'Verre', niveau: 2 }, { name: 'Vide', niveau: 1 }])
			expect(chemin(valeurs, 'Fioles')).toBe('Emballages › Verre › Fioles')
			expect(chemin(valeurs, 'Fioles', null)).toBe('Fioles')
		})
	})
})
