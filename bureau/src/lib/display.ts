/** Libellés, dates et liens affichés dans le poste de bureau. */

const STATUS_LABELS: Record<string, string> = { Pending: 'En pause' }

export function statusLabel(status?: string | null) {
	return STATUS_LABELS[status || ''] || status || ''
}

export function formatDay(value?: string | null) {
	if (!value) return ''
	const [year, month, day] = value.slice(0, 10).split('-')
	return year && month && day ? `${day}/${month}/${year}` : value
}

export function shortDay(value?: string | null) {
	return formatDay(value).slice(0, 5)
}

/** Lien vers le formulaire du Desk : « Sales Order » devient « sales-order ». */
export function deskUrl(doctype: string, name: string) {
	return `/app/${doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`
}

/** Initiales d'un nom (deux mots au plus), pour l'avatar du compte. */
export function initials(name?: string | null) {
	const words = (name || '').trim().split(/\s+/).filter(Boolean)
	return words.length ? words.slice(0, 2).map((word) => word[0].toUpperCase()).join('') : '?'
}
