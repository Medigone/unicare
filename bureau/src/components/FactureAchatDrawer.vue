<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { formatDay } from '@/lib/display'
import { factureAchatStatus as factureStatus, factureAchatTone as factureTone } from '@/lib/facturesAchat'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useFactureAchat } from '@/lib/useFactureAchat'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { facture, error, notFound, load, refresh } = useFactureAchat(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (facture.value) facture.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu de la facture d'achat">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Facture précédente" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Facture suivante" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				{{ facture?.actions.includes('payer') ? 'Payer' : 'Ouvrir la fiche' }}
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cette facture n'existe pas ou n'existe plus.</p>
			<p v-else-if="!facture" class="py-8 text-center text-ink-gray-6">Chargement de la facture…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ facture.name }}</h2>
						<StatusPill :status="factureStatus(facture.status)" :tone="factureTone(facture.status)" />
						<span v-if="facture.avoir" class="record-flag">Avoir</span>
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">
						<RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: facture.fournisseur } }">{{ facture.fournisseur_label }}</RouterLink>
						· {{ formatDay(facture.date) }}<template v-if="facture.numero_fournisseur"> · nº {{ facture.numero_fournisseur }}</template>
					</p>
					<TagEditor class="mt-1.5" doctype="Purchase Invoice" :name="facture.name" :modified="facture.modified" :tags="facture.tags" :can-edit="true" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(facture.total_ttc) }} DA</dd></div>
					<div><dt>Reste à payer</dt><dd class="tabular-nums" :class="facture.reste > 0 && 'text-tone-red'">{{ formatAmount(facture.reste) }} DA</dd></div>
					<div><dt>Échéance</dt><dd class="tabular-nums">{{ formatDay(facture.echeance) || '—' }}</dd></div>
					<div><dt>Payé</dt><dd class="tabular-nums">{{ formatAmount(facture.paye) }} DA</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Lignes</h3>
					<div v-for="line in facture.lignes.slice(0, 6)" :key="line.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="line.designation">{{ line.designation }}</span>
						<span class="flex-none tabular-nums text-ink-gray-7">{{ formatQty(line.quantite) }} {{ line.unite }} · {{ formatAmount(line.montant) }} DA</span>
					</div>
					<button v-if="facture.lignes.length > 6" type="button" class="self-start text-sm text-link" @click="emit('open')">Voir les {{ facture.lignes.length }} lignes</button>
				</section>

				<section v-if="facture.paiements?.length" class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Paiements</h3>
					<div v-for="row in facture.paiements" :key="row.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate">{{ formatDay(row.date) }} · {{ row.mode || '—' }}<template v-if="row.reference"> · {{ row.reference }}</template></span>
						<span class="flex-none tabular-nums">{{ formatAmount(row.montant) }} DA</span>
					</div>
				</section>
			</template>
		</div>
	</aside>
</template>
