import { describe, expect, it } from 'vitest'
import { pieceLink } from './fiches'

describe('fiches du bureau', () => {
	it('ouvre la fiche du bureau quand elle existe, le Desk sinon', () => {
		expect(pieceLink('Batch', 'FS-0001')).toEqual({ to: { name: 'Lot', params: { id: 'FS-0001' } } })
		expect(pieceLink('Ordre de Conditionnement', 'OC-1')).toEqual({ to: { name: 'OrdreFiche', params: { id: 'OC-1' } } })
		expect(pieceLink('Journal Entry', 'JV-1')).toEqual({ href: '/app/journal-entry/JV-1' })
	})
})
