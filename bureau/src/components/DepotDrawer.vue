<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatAmount } from '@/lib/clients'
import { useDepot } from '@/lib/useDepot'
import { useDrawerControls } from '@/lib/useDrawerControls'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { depot, error, notFound, load, refresh } = useDepot(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (depot.value) depot.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du dépôt">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Dépôt précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Dépôt suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
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
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Ce dépôt n'existe pas ou n'existe plus.</p>
			<p v-else-if="!depot" class="py-8 text-center text-ink-gray-6">Chargement du dépôt…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold">{{ depot.depot }}</h2>
						<StatusPill v-if="depot.desactive" status="Désactivé" tone="gray" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">{{ [depot.name, depot.parent].filter(Boolean).join(' · ') }}</p>
					<TagEditor class="mt-1.5" doctype="Warehouse" :name="depot.name" :modified="depot.modified" :tags="depot.tags" :can-edit="depot.can_edit" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Type</dt><dd class="truncate">{{ depot.type || '—' }}</dd></div>
					<div><dt>Groupe</dt><dd class="truncate">{{ depot.parent || '—' }}</dd></div>
					<div v-if="depot.articles !== null"><dt>Articles en stock</dt><dd class="tabular-nums">{{ depot.articles }}</dd></div>
					<div v-if="depot.valeur !== null"><dt>Valeur du stock</dt><dd class="tabular-nums">{{ formatAmount(depot.valeur) }} DA</dd></div>
				</dl>
			</template>
		</div>
	</aside>
</template>
