<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatQty } from '@/lib/articles'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useRecette } from '@/lib/useRecette'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { recette, error, notFound, load, refresh } = useRecette(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (recette.value) recette.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu de la recette">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Recette précédente" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Recette suivante" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">Ouvrir la fiche<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cette recette n'existe pas ou n'existe plus.</p>
			<p v-else-if="!recette" class="py-8 text-center text-ink-gray-6">Chargement de la recette…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold">{{ recette.designation }}</h2>
						<StatusPill :status="recette.actif ? 'Active' : 'Inactive'" :tone="recette.actif ? 'green' : 'gray'" />
					</div>
					<p class="mt-0.5 text-sm tabular-nums text-ink-gray-7">{{ recette.name }}</p>
					<TagEditor class="mt-1.5" doctype="Recette de Conditionnement" :name="recette.name" :modified="recette.modified" :tags="recette.tags" :can-edit="true" @changed="onTags" />
				</div>
				<dl class="bureau-drawer-facts">
					<div><dt>Donnée pour</dt><dd class="tabular-nums">{{ formatQty(recette.quantite_base) }} {{ recette.unite }}</dd></div>
					<div><dt>Rendement visé</dt><dd class="tabular-nums">{{ String(recette.rendement).replace('.', ',') }} %</dd></div>
					<div><dt>Rendement réel moyen</dt><dd class="tabular-nums">{{ recette.rendement_moyen === null ? '—' : `${String(recette.rendement_moyen).replace('.', ',')} % sur ${recette.ordres_termines} ordre${recette.ordres_termines > 1 ? 's' : ''}` }}</dd></div>
					<div><dt>Ordres</dt><dd class="tabular-nums">{{ recette.nb_ordres }}</dd></div>
				</dl>
				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Matières pour {{ formatQty(recette.quantite_base) }} {{ recette.unite }}</h3>
					<div v-for="row in recette.ingredients" :key="row.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="row.designation">{{ row.designation }} <span class="text-xs text-ink-gray-6">{{ row.type }}</span></span>
						<span class="flex-none tabular-nums">{{ formatQty(row.quantite) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></span>
					</div>
				</section>
			</template>
		</div>
	</aside>
</template>
