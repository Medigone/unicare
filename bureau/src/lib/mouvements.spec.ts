import { describe, expect, it } from 'vitest'
import { mouvementLinesForServer, MOUVEMENT_VIEWS, validateMouvement, type MouvementDraftLine } from './mouvements'

const line = (values: Partial<MouvementDraftLine> = {}): MouvementDraftLine => ({ key: 1, article: 'A', designation: 'A', unite: 'U', avec_lot: false, quantite: '2', lot: '', peremption: '', ...values })

describe('mouvements de stock', () => {
	it('demande les dépôts que la nature exige', () => {
		expect(validateMouvement({ nature: '', source: '', cible: '', lignes: [line()] }).nature).toBeTruthy()
		expect(validateMouvement({ nature: 'transfert', source: '', cible: 'P', lignes: [line()] }).source).toBeTruthy()
		expect(validateMouvement({ nature: 'transfert', source: 'M', cible: 'M', lignes: [line()] }).cible).toBeTruthy()
		expect(validateMouvement({ nature: 'sortie', source: 'M', cible: '', lignes: [line()] })).toEqual({})
		expect(validateMouvement({ nature: 'entree', source: '', cible: 'M', lignes: [line({ quantite: '0' })] }).ligne).toEqual({ 1: 'Quantité positive attendue.' })
	})

	it("n'envoie le lot et la péremption que là où ils servent", () => {
		const lines = [line({ avec_lot: true, lot: ' L1 ', peremption: '2027-01-01', quantite: '1,5' }), line({ key: 2, lot: 'ignoré' }), line({ key: 3, article: '' })]
		expect(mouvementLinesForServer(lines, 'entree')).toEqual([
			{ article: 'A', quantite: 1.5, lot: 'L1', peremption: '2027-01-01' },
			{ article: 'A', quantite: 2, lot: null, peremption: null },
		])
		expect(mouvementLinesForServer(lines, 'sortie')[0].peremption).toBeNull()
	})

	it('a les mêmes vues que le serveur', () => {
		expect(MOUVEMENT_VIEWS.map((view) => view.key)).toEqual(['all', 'brouillons', 'transferts', 'entrees', 'sorties', 'ordres', 'annules'])
	})
})
