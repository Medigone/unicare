<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import TagEditor from './TagEditor.vue'
import { formatQty } from '@/lib/articles'
import { useArticle } from '@/lib/useArticle'
import { useDrawerControls } from '@/lib/useDrawerControls'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { article, error, notFound, load, refresh } = useArticle(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (article.value) article.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu de l'article">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Article précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Article suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
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
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cet article n'existe pas ou n'existe plus.</p>
			<p v-else-if="!article" class="py-8 text-center text-ink-gray-6">Chargement de l'article…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold">{{ article.designation }}</h2>
						<span v-if="article.disabled" class="record-flag">Désactivé</span>
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">{{ [article.type, article.name, article.groupe].filter(Boolean).join(' · ') }}</p>
					<TagEditor class="mt-1.5" doctype="Item" :name="article.name" :modified="article.modified" :tags="article.tags" :can-edit="article.can_edit" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Unité de stock</dt><dd>{{ article.uom || '—' }}</dd></div>
					<div v-if="article.stock !== null"><dt>Stock</dt><dd class="tabular-nums">{{ formatQty(article.stock) }} {{ article.uom }}</dd></div>
					<div><dt>Géré par lots</dt><dd>{{ article.has_batch_no ? 'Oui' : 'Non' }}</dd></div>
					<div><dt>Conservation</dt><dd class="tabular-nums">{{ article.shelf_life_in_days ? `${article.shelf_life_in_days} jours` : '—' }}</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Description</h3>
					<p v-if="article.description" class="whitespace-pre-line">{{ article.description }}</p>
					<p v-else class="text-ink-gray-6">Aucune description.</p>
				</section>

				<section v-if="article.barcodes.length" class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Codes-barres</h3>
					<p class="tabular-nums">{{ article.barcodes.join(', ') }}</p>
				</section>
			</template>
		</div>
	</aside>
</template>
