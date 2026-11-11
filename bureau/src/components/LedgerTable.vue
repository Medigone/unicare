<script setup lang="ts">
import { useRouter } from 'vue-router'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { deskUrl, formatDay } from '@/lib/display'
import { pieceLabel, signedQty, type LedgerRow } from '@/lib/stock'

/** Grand livre de stock : une ligne par mouvement, avec le solde après mouvement. Colonnes masquables selon l'écran. */
const props = withDefaults(defineProps<{ rows: LedgerRow[]; showArticle?: boolean; showDepot?: boolean; showLots?: boolean; empty?: string }>(), {
	showArticle: true,
	showDepot: true,
	showLots: true,
	empty: 'Aucun mouvement.',
})

const router = useRouter()
const fiche = (row: LedgerRow) => (row.fiche && router.hasRoute(row.fiche) ? { name: row.fiche, params: { id: row.piece } } : null)
</script>

<template>
	<p v-if="!props.rows.length" class="text-ink-gray-6">{{ empty }}</p>
	<div v-else class="ref-scroll"><table class="ref-table">
		<thead><tr><th>Date</th><th>Pièce</th><th v-if="showArticle">Article</th><th v-if="showDepot">Dépôt</th><th v-if="showLots">Lot</th><th class="end">Quantité</th><th class="end">Solde</th><th class="end">Valeur (DA)</th></tr></thead>
		<tbody>
			<tr v-for="(row, index) in rows" :key="`${row.piece}-${row.article}-${row.depot}-${index}`">
				<td class="tabular-nums">{{ formatDay(row.date) }}<span v-if="row.heure" class="block text-xs text-ink-gray-6">{{ row.heure }}</span></td>
				<td>
					<span class="block text-xs text-ink-gray-6">{{ pieceLabel(row.piece_type) }}</span>
					<RouterLink v-if="fiche(row)" class="ref-link tabular-nums" :to="fiche(row)!">{{ row.piece }}</RouterLink>
					<a v-else class="ref-link tabular-nums" :href="deskUrl(row.piece_type, row.piece)" target="_blank" rel="noopener noreferrer">{{ row.piece }}</a>
				</td>
				<td v-if="showArticle"><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: row.article } }">{{ row.designation }}</RouterLink></td>
				<td v-if="showDepot">{{ row.depot }}</td>
				<td v-if="showLots" class="tabular-nums">{{ row.lots.join(', ') || '—' }}</td>
				<td class="end tabular-nums" :class="row.quantite > 0 ? 'text-tone-green' : 'text-tone-red'">{{ signedQty(row.quantite) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></td>
				<td class="end tabular-nums">{{ formatQty(row.solde) }}</td>
				<td class="end tabular-nums">{{ formatAmount(row.valeur) }}</td>
			</tr>
		</tbody>
	</table></div>
</template>
