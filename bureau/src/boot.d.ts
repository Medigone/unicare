/** Données de démarrage posées par la page serveur (unicare/www/bureau.py, `get_boot`). */
declare global {
	interface Window {
		can_access?: boolean
		postes?: { key: string; label: string }[]
		droits?: Record<string, { read: boolean; create: boolean }>
		user_fullname?: string | null
	}
}

export {}
