<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatAmount } from '@/lib/clients'
import { formatDay } from '@/lib/display'
import { PAIEMENT_STATUS } from '@/lib/paiements'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { usePaiement } from '@/lib/usePaiement'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { paiement, error, notFound, load, refresh } = usePaiement(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (paiement.value) paiement.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du paiement">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Paiement précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Paiement suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				{{ paiement?.status === 'Draft' ? 'Relire et valider' : 'Ouvrir la fiche' }}
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Ce paiement n'existe pas ou n'existe plus.</p>
			<p v-else-if="!paiement" class="py-8 text-center text-ink-gray-6">Chargement du paiement…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ paiement.name }}</h2>
						<StatusPill :status="PAIEMENT_STATUS[paiement.status]" :tone="paiement.status === 'Submitted' ? 'green' : paiement.status === 'Draft' ? 'amber' : 'gray'" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">{{ paiement.type_label }} · {{ paiement.tiers_label }} · {{ formatDay(paiement.date) }}</p>
					<TagEditor class="mt-1.5" doctype="Payment Entry" :name="paiement.name" :modified="paiement.modified" :tags="paiement.tags" :can-edit="true" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Montant</dt><dd class="tabular-nums">{{ formatAmount(paiement.montant) }} DA</dd></div>
					<div><dt>Mode</dt><dd class="truncate">{{ paiement.mode || '—' }}<template v-if="paiement.reference"> · {{ paiement.reference }}</template></dd></div>
					<div><dt>Affecté</dt><dd class="tabular-nums">{{ formatAmount(paiement.affecte) }} DA</dd></div>
					<div><dt>Avance</dt><dd class="tabular-nums">{{ formatAmount(paiement.non_affecte) }} DA</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Rapprochement</h3>
					<p v-if="!paiement.affectations.length" class="text-ink-gray-6">Aucune pièce : le paiement est une avance.</p>
					<div v-for="row in paiement.affectations" :key="row.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate tabular-nums">{{ row.name }}</span>
						<span class="flex-none tabular-nums">{{ formatAmount(row.montant) }} DA</span>
					</div>
				</section>
			</template>
		</div>
	</aside>
</template>
