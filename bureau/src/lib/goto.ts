/** « Aller à… » : la liste des pages du poste et leur filtre par la saisie. */
import type { Component } from 'vue'

export interface GotoPage {
	id: string
	label: string
	/** Le module de la page ; vide pour un module qui est lui-même une page (Accueil). */
	module: string
	icon: Component
	to?: { name: string }
	href?: string
}

/** Sans accents ni casse : « fact » trouve « Factures d'achat », « stoc » le module Stock. */
export function normalize(value: string) {
	return value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim()
}

/**
 * Pages dont le nom ou le module contient chaque mot saisi. Celles dont le nom commence par la saisie passent
 * devant ; sans saisie, toutes, dans l'ordre du menu.
 */
export function filterPages(pages: GotoPage[], query: string) {
	const words = normalize(query).split(' ').filter(Boolean)
	if (!words.length) return pages
	const scored = pages
		.map((page, index) => {
			const label = normalize(page.label)
			const text = `${label} ${normalize(page.module)}`
			if (!words.every((word) => text.includes(word))) return null
			return { page, index, score: label.startsWith(words[0]) ? 0 : label.includes(words[0]) ? 1 : 2 }
		})
		.filter((entry): entry is { page: GotoPage; index: number; score: number } => entry !== null)
	return scored.sort((a, b) => a.score - b.score || a.index - b.index).map((entry) => entry.page)
}
