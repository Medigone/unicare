<script setup lang="ts">
import { computed } from 'vue'
import LucideBoxes from '~icons/lucide/boxes'
import LucideCoins from '~icons/lucide/coins'
import LucideTarget from '~icons/lucide/target'
import LucideWarehouse from '~icons/lucide/warehouse'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import LedgerTable from './LedgerTable.vue'
import RecordHeader from './RecordHeader.vue'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { formatDay } from '@/lib/display'
import { niveauStock } from '@/lib/etatStock'
import { useLigneStock } from '@/lib/useLigneStock'

/** Fiche d'une ligne de stock : un article dans un dépôt, ses quantités, ses lots et son historique. Lecture seule. */
const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: [] }>()

const { ligne, error, notFound, notice, noticeTone, load, refresh } = useLigneStock(
	() => props.id,
	() => emit('changed'),
	true,
)
defineExpose({ refresh, ligne })

const NIVEAUX = { negatif: ['Stock négatif', 'red'], rupture: ['En rupture', 'red'], bas: ['Sous le seuil', 'amber'] } as const
const niveau = computed(() => (ligne.value ? niveauStock(ligne.value) : null))
</script>

<template>
	<main class="bureau-main">
		<div v-if="error" role="alert" class="card p-3.5 text-tone-red">
			{{ error }}
			<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
		</div>
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cette ligne de stock n'existe plus.</div>
		<div v-else-if="!ligne" class="card p-8 text-center text-ink-gray-6">Chargement…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ ligne.designation }}</template>
				<template #flags><StatusPill v-if="niveau" :status="NIVEAUX[niveau][0]" :tone="NIVEAUX[niveau][1]" /></template>
				<template #sub>
					<RouterLink class="ref-link tabular-nums" :to="{ name: 'Article', params: { id: ligne.article } }">{{ ligne.article }}</RouterLink>
					<RouterLink class="ref-link" :to="{ name: 'Depot', params: { id: ligne.depot } }">{{ ligne.depot }}</RouterLink>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Quantités">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBoxes aria-hidden="true" />En stock</dt><dd class="tabular-nums" :class="niveau && niveau !== 'bas' ? 'text-tone-red' : niveau === 'bas' && 'text-tone-amber'">{{ formatQty(ligne.quantite) }} {{ ligne.unite }}</dd></div>
							<div><dt>Réservé (commandes client)</dt><dd class="tabular-nums" :class="!ligne.reserve && 'record-fact-none'">{{ formatQty(ligne.reserve) }}</dd></div>
							<div><dt>Commandé (achats en cours)</dt><dd class="tabular-nums" :class="!ligne.commande && 'record-fact-none'">{{ formatQty(ligne.commande) }}</dd></div>
							<div><dt>Projeté</dt><dd class="tabular-nums">{{ formatQty(ligne.projete) }}</dd></div>
							<div><dt><LucideTarget aria-hidden="true" />Seuil de réapprovisionnement</dt><dd class="tabular-nums" :class="ligne.seuil === null && 'record-fact-none'">{{ ligne.seuil === null ? 'Aucun' : formatQty(ligne.seuil) }}</dd></div>
							<div><dt><LucideCoins aria-hidden="true" />Valeur</dt><dd class="tabular-nums">{{ formatAmount(ligne.valeur) }} DA<span class="block text-xs font-normal text-ink-gray-6">{{ formatAmount(ligne.taux) }} DA l'unité</span></dd></div>
							<div><dt><LucideWarehouse aria-hidden="true" />Dépôt</dt><dd><RouterLink class="ref-link" :to="{ name: 'Depot', params: { id: ligne.depot } }">{{ ligne.depot }}</RouterLink></dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<div class="bureau-detail">
						<div class="bureau-center">
							<section v-if="ligne.lots" class="card ref-card">
								<h3>Lots dans ce dépôt</h3>
								<p v-if="!ligne.lots.length" class="text-ink-gray-6">Aucun lot en stock.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Lot</th><th>Péremption</th><th class="end">Quantité</th></tr></thead>
									<tbody>
										<tr v-for="lot in ligne.lots" :key="lot.lot">
											<td class="tabular-nums"><RouterLink v-if="$router.hasRoute('Lot')" class="ref-link" :to="{ name: 'Lot', params: { id: lot.lot } }">{{ lot.lot }}</RouterLink><template v-else>{{ lot.lot }}</template></td>
											<td class="tabular-nums">{{ formatDay(lot.peremption) || '—' }}</td>
											<td class="end tabular-nums">{{ formatQty(lot.qty) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
							<section v-if="ligne.mouvements" class="card ref-card">
								<h3>Historique</h3>
								<LedgerTable :rows="ligne.mouvements" :show-article="false" :show-depot="false" :show-lots="Boolean(ligne.avec_lot)" empty="Aucun mouvement pour cet article dans ce dépôt." />
							</section>
						</div>
					</div>
				</div>
			</div>
		</template>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
