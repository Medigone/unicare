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
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useInventaire } from '@/lib/useInventaire'
import { signedQty } from '@/lib/stock'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { inventaire, error, notFound, load, refresh } = useInventaire(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (inventaire.value) inventaire.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu de l'inventaire">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Inventaire précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Inventaire suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				{{ inventaire?.docstatus === 0 ? 'Compter' : 'Ouvrir la fiche' }}
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cet inventaire n'existe pas ou n'existe plus.</p>
			<p v-else-if="!inventaire" class="py-8 text-center text-ink-gray-6">Chargement de l'inventaire…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ inventaire.name }}</h2>
						<StatusPill :status="inventaire.status" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">{{ inventaire.depot || '—' }} · {{ formatDay(inventaire.date) }}</p>
					<TagEditor class="mt-1.5" doctype="Stock Reconciliation" :name="inventaire.name" :modified="inventaire.modified" :tags="inventaire.tags" :can-edit="true" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Lignes</dt><dd class="tabular-nums">{{ inventaire.resume.lignes }}</dd></div>
					<div><dt>Lignes avec écart</dt><dd class="tabular-nums">{{ inventaire.resume.ecarts }}</dd></div>
					<div><dt>Surplus / manquants</dt><dd class="tabular-nums">{{ signedQty(inventaire.resume.plus) }} / {{ signedQty(inventaire.resume.moins) }}</dd></div>
					<div><dt>Écart de valeur</dt><dd class="tabular-nums" :class="inventaire.resume.valeur < 0 ? 'text-tone-red' : inventaire.resume.valeur > 0 && 'text-tone-green'">{{ formatAmount(inventaire.resume.valeur) }} DA</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Écarts</h3>
					<p v-if="!inventaire.lignes.some((line) => line.ecart)" class="text-ink-gray-6">Aucun écart pour l'instant.</p>
					<div v-for="line in inventaire.lignes.filter((row) => row.ecart).slice(0, 6)" :key="line.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="line.designation">{{ line.designation }}<span v-if="line.lot" class="text-xs text-ink-gray-6"> · {{ line.lot }}</span></span>
						<span class="flex-none tabular-nums" :class="line.ecart < 0 ? 'text-tone-red' : 'text-tone-green'">{{ signedQty(line.ecart) }} <span class="text-xs text-ink-gray-6">({{ formatQty(line.compte) }} / {{ formatQty(line.theorique) }})</span></span>
					</div>
				</section>
			</template>
		</div>
	</aside>
</template>
