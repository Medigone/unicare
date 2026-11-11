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
import { natureLabel } from '@/lib/mouvements'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useMouvement } from '@/lib/useMouvement'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { mouvement, error, notFound, load, refresh } = useMouvement(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (mouvement.value) mouvement.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du mouvement">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Mouvement précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Mouvement suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				Ouvrir la fiche
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Ce mouvement n'existe pas ou n'existe plus.</p>
			<p v-else-if="!mouvement" class="py-8 text-center text-ink-gray-6">Chargement du mouvement…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ mouvement.name }}</h2>
						<StatusPill :status="mouvement.status" />
						<span v-if="mouvement.depuis_ordre" class="record-flag">Ordre</span>
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">{{ natureLabel(mouvement.nature) }} · {{ formatDay(mouvement.date) }}<template v-if="mouvement.ordre"> · {{ mouvement.ordre }}</template></p>
					<TagEditor class="mt-1.5" doctype="Stock Entry" :name="mouvement.name" :modified="mouvement.modified" :tags="mouvement.tags" :can-edit="true" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Départ</dt><dd class="truncate">{{ mouvement.lignes[0]?.source || '—' }}</dd></div>
					<div><dt>Arrivée</dt><dd class="truncate">{{ mouvement.lignes[0]?.cible || '—' }}</dd></div>
					<div><dt>Valeur</dt><dd class="tabular-nums">{{ formatAmount(mouvement.valeur_sortie || mouvement.valeur_entree) }} DA</dd></div>
					<div><dt>Remarque</dt><dd class="truncate">{{ mouvement.remarque || '—' }}</dd></div>
				</dl>

				<p v-if="mouvement.blocked.length" role="status" class="rounded-control tone-amber px-3 py-2 text-sm">{{ mouvement.blocked.join(' ') }}</p>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Lignes</h3>
					<div v-for="row in mouvement.lignes.slice(0, 6)" :key="row.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="row.designation">{{ row.designation }}</span>
						<span class="flex-none text-right tabular-nums text-ink-gray-7">
							{{ formatQty(row.quantite) }} {{ row.unite }}
							<span v-if="row.lots.length" class="block text-xs">lot {{ row.lots.join(', ') }}</span>
						</span>
					</div>
					<button v-if="mouvement.lignes.length > 6" type="button" class="self-start text-sm text-link" @click="emit('open')">Voir les {{ mouvement.lignes.length }} lignes</button>
				</section>
			</template>
		</div>
	</aside>
</template>
