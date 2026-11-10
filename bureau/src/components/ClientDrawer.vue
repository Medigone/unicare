<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideMail from '~icons/lucide/mail'
import LucideMapPin from '~icons/lucide/map-pin'
import LucidePhone from '~icons/lucide/phone'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatAmount, SOLDE_DOCTYPE } from '@/lib/clients'
import { canRead } from '@/lib/droits'
import { useClient } from '@/lib/useClient'
import { useDrawerControls } from '@/lib/useDrawerControls'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { client, error, notFound, load, refresh } = useClient(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

const contacts = computed(() => client.value?.contacts ?? [])
const pieces = computed(() => (client.value?.pieces ?? []).filter((piece) => piece.numero))
function onTags(tags: string[]) {
	if (client.value) client.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du client">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Client précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Client suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
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
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Ce client n'existe pas ou n'existe plus.</p>
			<p v-else-if="!client" class="py-8 text-center text-ink-gray-6">Chargement du client…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold">{{ client.client }}</h2>
						<StatusPill :status="client.status" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">{{ [client.forme_juridique, client.name, client.commune_label, client.wilaya].filter(Boolean).join(' · ') }}</p>
					<TagEditor class="mt-1.5" doctype="Customer" :name="client.name" :modified="client.modified" :tags="client.tags" :can-edit="client.can_edit" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Catégorie</dt><dd class="truncate">{{ client.categorie || '—' }}</dd></div>
					<div><dt>Wilaya</dt><dd class="truncate">{{ client.wilaya || '—' }}</dd></div>
					<div><dt>Région</dt><dd class="truncate">{{ client.region || '—' }}</dd></div>
					<div v-if="canRead(SOLDE_DOCTYPE) && client.solde !== null"><dt>Solde</dt><dd class="tabular-nums">{{ client.solde ? `${formatAmount(client.solde)} DA` : 'Aucun' }}</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Contacts</h3>
					<template v-if="contacts.length">
						<div v-for="(contact, index) in contacts.slice(0, 3)" :key="index" class="flex flex-col gap-0.5">
							<p>
								<span class="font-semibold text-ink-gray-9">{{ contact.nom || 'Sans nom' }}</span>
								<span v-if="contact.fonction" class="text-ink-gray-6"> · {{ contact.fonction }}</span>
								<span v-if="contact.principal" class="text-ink-gray-6"> · principal</span>
							</p>
							<p class="contact-links">
								<a v-if="contact.telephone" class="ref-link tabular-nums" :href="`tel:${contact.telephone}`"><LucidePhone class="h-3.5 w-3.5" aria-hidden="true" />{{ contact.telephone }}</a>
								<a v-if="contact.email" class="ref-link" :href="`mailto:${contact.email}`"><LucideMail class="h-3.5 w-3.5" aria-hidden="true" />{{ contact.email }}</a>
							</p>
						</div>
						<button v-if="contacts.length > 3" type="button" class="self-start text-sm text-link" @click="emit('open')">Voir les {{ contacts.length }} contacts</button>
					</template>
					<p v-else class="text-ink-gray-6">Aucun contact enregistré.</p>
				</section>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Adresse</h3>
					<p v-if="client.adresse" class="whitespace-pre-line">{{ client.adresse }}</p>
					<p>{{ [client.commune_label, client.wilaya].filter(Boolean).join(', ') || 'Commune non renseignée.' }}</p>
					<a v-if="client.map_url" class="ref-link self-start" :href="client.map_url" target="_blank" rel="noopener noreferrer"><LucideMapPin class="h-3.5 w-3.5" aria-hidden="true" />Voir sur la carte</a>
				</section>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Pièces administratives</h3>
					<dl v-if="pieces.length" class="info-grid">
						<template v-for="piece in pieces" :key="piece.key">
							<dt>{{ piece.label }}</dt>
							<dd class="tabular-nums">
								<a v-if="piece.fichier" class="ref-link" :href="piece.fichier" target="_blank" rel="noopener noreferrer">{{ piece.numero }}</a>
								<template v-else>{{ piece.numero }}</template>
							</dd>
						</template>
					</dl>
					<p v-else class="text-ink-gray-6">Aucune pièce renseignée.</p>
				</section>
			</template>
		</div>
	</aside>
</template>
