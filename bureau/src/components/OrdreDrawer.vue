<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import OrdreSteps from './OrdreSteps.vue'
import TagEditor from './TagEditor.vue'
import { formatQty } from '@/lib/articles'
import { echeanceText, ETAPE_TONES } from '@/lib/ordres'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useOrdre } from '@/lib/useOrdre'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { ordre, error, notFound, load, refresh } = useOrdre(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

// Le bouton dit ce que la fiche permettra de faire ensuite.
const openLabel = computed(() => {
	const actions = ordre.value?.actions ?? []
	if (actions.includes('preparer') || actions.includes('modifier')) return 'Planifier'
	if (actions.includes('demarrer')) return 'Démarrer'
	if (actions.includes('cloturer')) return 'Saisir et clôturer'
	return 'Ouvrir la fiche'
})

function onTags(tags: string[]) {
	if (ordre.value) ordre.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu de l'ordre">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Ordre précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Ordre suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				{{ openLabel }}
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cet ordre n'existe pas ou n'existe plus.</p>
			<p v-else-if="!ordre" class="py-8 text-center text-ink-gray-6">Chargement de l'ordre…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold">{{ ordre.designation }}</h2>
						<StatusPill :status="ordre.etape" :tone="ETAPE_TONES[ordre.state]" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">
						<span class="tabular-nums">{{ ordre.name }}</span> · {{ formatQty(ordre.qty_prevue) }} {{ ordre.unite }} ·
						<span :class="ordre.retard && 'font-medium text-tone-red'">{{ echeanceText(ordre.date_prevue, ordre.retard) }}</span>
					</p>
					<TagEditor class="mt-1.5" doctype="Ordre de Conditionnement" :name="ordre.name" :modified="ordre.modified" :tags="ordre.tags" :can-edit="true" @changed="onTags" />
				</div>

				<OrdreSteps :etapes="ordre.etapes" compact />

				<section v-if="ordre.manques.length" class="ordre-manques">
					<h3>Ce qui manque pour préparer</h3>
					<ol>
						<li v-for="(manque, index) in ordre.manques" :key="index">{{ manque.texte }}</li>
					</ol>
				</section>

				<dl class="bureau-drawer-facts">
					<div><dt>Recette</dt><dd>{{ ordre.recette || '—' }}</dd></div>
					<div v-if="ordre.state === 'Terminé'"><dt>Produit</dt><dd class="tabular-nums">{{ formatQty(ordre.qty_reelle) }} sur {{ formatQty(ordre.qty_prevue) }} · {{ String(ordre.rendement).replace('.', ',') }} %</dd></div>
					<div><dt>Lot produit fini</dt><dd class="tabular-nums">{{ ordre.lot_pf || '—' }}</dd></div>
					<div><dt>Contrôles</dt><dd>{{ ordre.checklist.filter((row) => row.conforme).length }} sur {{ ordre.checklist.length }}</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Matières</h3>
					<div v-for="line in ordre.matieres" :key="line.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="line.designation">{{ line.designation }}<span v-if="line.lot" class="text-xs text-ink-gray-6"> · {{ line.lot }}</span></span>
						<span class="flex-none tabular-nums">{{ formatQty(line.prevu + line.complement) }} <span class="text-xs text-ink-gray-6">{{ line.unite }}</span></span>
					</div>
				</section>
			</template>
		</div>
	</aside>
</template>
