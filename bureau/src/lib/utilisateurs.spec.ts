import { describe, expect, it } from 'vitest'
import { derniereConnexion, rolesLabels, utilisateurErreur, type UtilisateurForm, entreDansLeBureau, genererMotDePasse, initiales } from './utilisateurs'

const form = (values: Partial<UtilisateurForm>): UtilisateurForm => ({ email: 'a@b.dz', prenom: 'Amel', nom_famille: '', actif: true, roles: [], mot_de_passe: 'motdepasse', ...values })

describe('utilisateurs', () => {
	it('vérifie la saisie', () => {
		expect(utilisateurErreur(form({}), true)).toBeNull()
		expect(utilisateurErreur(form({ email: 'pas-une-adresse' }), true)).toMatch(/adresse e-mail/)
		expect(utilisateurErreur(form({ prenom: ' ' }), false)).toBe('Indiquez au moins le prénom.')
		expect(utilisateurErreur(form({ mot_de_passe: 'court' }), true)).toMatch(/8 caractères/)
		expect(utilisateurErreur(form({ email: '', mot_de_passe: '' }), false)).toBeNull()
	})

	it('donne les rôles en clair', () => {
		const choix = [{ domaine: 'Ventes', roles: [{ role: 'Sales User', label: 'Commercial', aide: '' }, { role: 'Sales Manager', label: 'Responsable ventes', aide: '' }] }]
		expect(rolesLabels(['Sales Manager', 'Blogger'], choix)).toEqual(['Responsable ventes'])
	})

	it('dit quand le compte s\'est connecté', () => {
		const today = new Date(2026, 10, 18, 12)
		expect(derniereConnexion(null, today)).toBe('Jamais connecté')
		expect(derniereConnexion('2026-11-18 08:00:00', today)).toBe("Aujourd'hui")
		expect(derniereConnexion('2026-11-17 23:00:00', today)).toBe('Hier')
		expect(derniereConnexion('2026-11-10 10:00:00', today)).toBe('Il y a 8 jours')
	})

	it('affiche des initiales', () => {
		expect(initiales('Nadia Hamdi')).toBe('NH')
		expect(initiales('Karim Ben Salem')).toBe('KS')
		expect(initiales('admin')).toBe('AD')
	})

	it('génère un mot de passe facile à dicter', () => {
		const mdp = genererMotDePasse()
		expect(mdp).toMatch(/^[A-Z][a-z]+-[A-Z][a-z]+-\d{4}$/)
		expect(mdp.length).toBeGreaterThanOrEqual(8)
		expect(genererMotDePasse(() => 0)).toBe('Cedre-Olive-1000')
	})

	it("dit si les rôles ouvrent le bureau", () => {
		expect(entreDansLeBureau(['Sales User'], ['Sales User', 'System Manager'])).toBe(true)
		expect(entreDansLeBureau(['Item Manager'], ['Sales User'])).toBe(false)
	})
})
