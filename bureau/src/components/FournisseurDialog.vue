<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import LucideInfo from '~icons/lucide/info'
import LucideSearch from '~icons/lucide/search'
import LucideX from '~icons/lucide/x'
import FormDialog from '@shared/components/FormDialog.vue'
import { createFournisseur, getFournisseurOptions, searchCommunes, searchFournisseurs, updateFournisseur } from '@/lib/api'
import type { CommuneChoice } from '@/lib/clients'
import { changedFournisseurValues, fournisseurFormValues, normalizeName, validateFournisseur, type FournisseurChoice, type FournisseurDetail, type FournisseurField, type FournisseurOptions, type FournisseurValues } from '@/lib/fournisseurs'

/** Nouveau fournisseur, ou modification d'un fournisseur : la même fenêtre. Le contact principal ne se saisit qu'à la création. */
const props = defineProps<{ fournisseur?: FournisseurDetail }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [fournisseur: FournisseurDetail] }>()

const editing = computed(() => Boolean(props.fournisseur))
const EMPTY: FournisseurValues = { supplier_name: '', status: '', categorie: '', commune: '', contact: '', fonction: '', contact_telephone: '', contact_email: '', rc: '', nif: '', nis: '', ai: '' }
const initial: FournisseurValues = props.fournisseur ? { ...EMPTY, ...fournisseurFormValues(props.fournisseur) } : { ...EMPTY }
const values = reactive<Record<FournisseurField, string>>({ ...(initial as Record<FournisseurField, string>) })
const options = ref<FournisseurOptions | null>(null)
const loadError = ref('')
const serverError = ref('')
const errors = ref<Partial<Record<FournisseurField, string>>>({})
const busy = ref(false)
const changes = computed(() => changedFournisseurValues(initial, values))
// À la création, toute saisie compte : la fermeture demande confirmation.
const dirty = computed(() => (editing.value ? Object.keys(changes.value).length > 0 : Object.entries(values).some(([field, value]) => value.trim() !== (initial[field as FournisseurField] ?? '').trim())))
const PIECES: { field: FournisseurField; label: string }[] = [
	{ field: 'rc', label: 'Nº RC' },
	{ field: 'nif', label: 'Nº NIF' },
	{ field: 'nis', label: 'Nº NIS' },
	{ field: 'ai', label: 'Nº AI' },
]

onMounted(async () => {
	try {
		options.value = await getFournisseurOptions()
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

function clearError(field: FournisseurField) {
	if (errors.value[field]) delete errors.value[field]
}
watch(
	() => ({ ...values }),
	(current, previous) => {
		for (const field of Object.keys(current) as FournisseurField[]) if (current[field] !== previous[field]) clearError(field)
	},
)

// Raison sociale : le serveur refuse un nom déjà pris. La fenêtre le dit dès la saisie.
const similar = ref<FournisseurChoice[]>([])
let lastName = 0
let nameTimer: ReturnType<typeof setTimeout> | null = null
watch(
	() => values.supplier_name,
	(name) => {
		if (nameTimer) clearTimeout(nameTimer)
		const query = normalizeName(name)
		if (query.length < 3) {
			similar.value = []
			return
		}
		nameTimer = setTimeout(async () => {
			const request = ++lastName
			try {
				const found = await searchFournisseurs(name)
				if (request === lastName) similar.value = found.filter((item) => item.name !== props.fournisseur?.name && normalizeName(item.label).includes(query)).slice(0, 3)
			} catch {
				// Le serveur refusera de toute façon un nom déjà pris.
			}
		}, 250)
	},
)

// Commune : la wilaya et la région en découlent sur le serveur. Une seule réponse compte, celle de la dernière frappe.
const communeLabel = ref(props.fournisseur?.commune_label ?? '')
const communeWilaya = ref(props.fournisseur?.wilaya ?? '')
const communeQuery = ref('')
const communes = ref<CommuneChoice[]>([])
const communesOpen = ref(false)
const communesSearched = ref(false)
const communeCursor = ref(0)
const communeInput = ref<HTMLInputElement | null>(null)
let lastCommune = 0
let communeTimer: ReturnType<typeof setTimeout> | null = null
async function runCommuneSearch() {
	const request = ++lastCommune
	try {
		const found = await searchCommunes(communeQuery.value)
		if (request !== lastCommune) return
		communes.value = found
		communesSearched.value = true
		communeCursor.value = 0
	} catch (e) {
		if (request === lastCommune) serverError.value = (e as Error).message
	}
}
watch(communeQuery, () => {
	if (values.commune) return
	communesOpen.value = true
	if (communeTimer) clearTimeout(communeTimer)
	communeTimer = setTimeout(runCommuneSearch, 200)
})
function openCommunes() {
	communesOpen.value = true
	if (!communesSearched.value) runCommuneSearch()
}
function pickCommune(choice?: CommuneChoice) {
	if (!choice) return
	values.commune = choice.name
	communeLabel.value = choice.commune || choice.name
	communeWilaya.value = choice.wilaya || ''
	communesOpen.value = false
}
async function changeCommune() {
	values.commune = ''
	communeLabel.value = ''
	communeWilaya.value = ''
	communeQuery.value = ''
	await nextTick()
	communeInput.value?.focus()
}
function onCommuneKey(event: KeyboardEvent) {
	if (event.key === 'Escape' && communesOpen.value) {
		event.stopPropagation()
		communesOpen.value = false
		return
	}
	const size = communes.value.length
	if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
		event.preventDefault()
		communesOpen.value = true
		if (size) communeCursor.value = (communeCursor.value + (event.key === 'ArrowDown' ? 1 : size - 1)) % size
	} else if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey && communesOpen.value) {
		event.preventDefault()
		pickCommune(communes.value[communeCursor.value])
	}
}
function onCommuneBlur(event: FocusEvent) {
	if (!(event.relatedTarget as HTMLElement | null)?.closest?.('.picker-menu')) communesOpen.value = false
}

async function submit() {
	if (busy.value) return
	errors.value = validateFournisseur(values, editing.value)
	serverError.value = ''
	if (Object.keys(errors.value).length) {
		await nextTick()
		document.querySelector<HTMLElement>('.dialog [aria-invalid="true"]')?.focus()
		return
	}
	if (props.fournisseur && !Object.keys(changes.value).length) {
		emit('close')
		return
	}
	busy.value = true
	try {
		if (props.fournisseur) {
			emit('saved', await updateFournisseur(props.fournisseur, changes.value))
		} else {
			const { status: _status, ...fields } = values
			const { name } = await createFournisseur(Object.fromEntries(Object.entries(fields).map(([field, value]) => [field, value.trim()])))
			emit('created', name)
		}
		emit('close')
	} catch (e) {
		// La saisie reste en place : rien n'est perdu si le serveur refuse.
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
onBeforeUnmount(() => {
	if (nameTimer) clearTimeout(nameTimer)
	if (communeTimer) clearTimeout(communeTimer)
})
</script>

<template>
	<FormDialog :title="editing ? 'Modifier le fournisseur' : 'Nouveau fournisseur'" :dirty="dirty" :busy="busy" :hint="editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>

		<div class="form-field">
			<label class="field-label" for="fournisseur-raison">Raison sociale <span class="req">obligatoire</span></label>
			<input id="fournisseur-raison" v-model="values.supplier_name" class="field-input" placeholder="Nom de la société" autocomplete="off" :aria-invalid="Boolean(errors.supplier_name)" />
			<p v-if="errors.supplier_name" class="field-error" role="alert">{{ errors.supplier_name }}</p>
			<p v-if="similar.length" class="field-note">
				<LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" />
				<span>
					Déjà enregistré :
					<template v-for="(item, index) in similar" :key="item.name">{{ index ? ', ' : '' }}<a class="ref-link" :href="`/bureau/fournisseurs/${encodeURIComponent(item.name)}`" target="_blank" rel="noopener noreferrer">{{ item.label }}</a><template v-if="item.wilaya"> ({{ item.wilaya }})</template><template v-if="item.disabled">, désactivé ou exclu</template></template>.
				</span>
			</p>
		</div>

		<div class="form-grid">
			<div v-if="editing" class="form-field">
				<label class="field-label" for="fournisseur-statut">Statut du fournisseur <span class="req">obligatoire</span></label>
				<select v-search id="fournisseur-statut" v-model="values.status" class="field-input" :aria-invalid="Boolean(errors.status)">
					<option v-if="!values.status" value="">Choisir…</option>
					<option v-for="item in options?.statuses ?? [values.status]" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="errors.status" class="field-error" role="alert">{{ errors.status }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="fournisseur-categorie">Catégorie <span class="req">obligatoire</span></label>
				<select v-search id="fournisseur-categorie" v-model="values.categorie" class="field-input" :aria-invalid="Boolean(errors.categorie)">
					<option value="">Choisir…</option>
					<option v-if="values.categorie && options && !options.categories.includes(values.categorie)" :value="values.categorie">{{ values.categorie }}</option>
					<option v-for="item in options?.categories" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="errors.categorie" class="field-error" role="alert">{{ errors.categorie }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="fournisseur-commune">Commune</label>
				<div v-if="values.commune" class="picked">
					<div class="flex min-w-0 flex-auto flex-wrap items-baseline gap-x-2">
						<strong class="font-semibold text-ink-gray-9">{{ communeLabel }}</strong>
						<span v-if="communeWilaya" class="text-sm text-ink-gray-6">Wilaya : {{ communeWilaya }}</span>
					</div>
					<button id="fournisseur-commune" type="button" class="comment-tool" aria-label="Changer de commune" title="Changer de commune" @click="changeCommune"><LucideX class="h-3.5 w-3.5" aria-hidden="true" /></button>
				</div>
				<div v-else class="relative">
					<LucideSearch class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-gray-5" aria-hidden="true" />
					<input
						id="fournisseur-commune"
						ref="communeInput"
						v-model="communeQuery"
						class="field-input pl-8"
						type="search"
						placeholder="Commune ou wilaya"
						autocomplete="off"
						role="combobox"
						aria-autocomplete="list"
						:aria-expanded="communesOpen"
						:aria-invalid="Boolean(errors.commune)"
						@focus="openCommunes"
						@click="openCommunes"
						@keydown="onCommuneKey"
						@blur="onCommuneBlur"
					/>
					<div v-if="communesOpen" class="app-menu picker-menu" role="listbox" aria-label="Communes">
						<button v-for="(choice, index) in communes" :key="choice.name" type="button" class="app-menu-item" role="option" :aria-selected="index === communeCursor" @mousedown.prevent @click="pickCommune(choice)" @pointerenter="communeCursor = index">
							<span class="min-w-0 flex-auto truncate">{{ choice.commune || choice.name }}</span>
							<span class="text-xs text-ink-gray-6">{{ choice.wilaya }}</span>
						</button>
						<p v-if="communesSearched && !communes.length" class="app-menu-title">Aucune commune ne correspond.</p>
						<p v-else-if="!communesSearched" class="app-menu-title">Recherche…</p>
					</div>
				</div>
				<p v-if="errors.commune" class="field-error" role="alert">{{ errors.commune }}</p>
			</div>
		</div>

		<template v-if="!editing">
			<h3 class="form-section">Contact principal</h3>
			<p class="field-note -mt-1"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Facultatif. Le contact est créé avec le fournisseur et lui est lié, comme sur le Desk.</span></p>
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="fournisseur-contact">Nom du contact</label>
					<input id="fournisseur-contact" v-model="values.contact" class="field-input" autocomplete="off" :aria-invalid="Boolean(errors.contact)" />
					<p v-if="errors.contact" class="field-error" role="alert">{{ errors.contact }}</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="fournisseur-fonction">Fonction</label>
					<input id="fournisseur-fonction" v-model="values.fonction" class="field-input" autocomplete="off" />
				</div>
				<div class="form-field">
					<label class="field-label" for="fournisseur-contact-telephone">Téléphone mobile</label>
					<input id="fournisseur-contact-telephone" v-model="values.contact_telephone" class="field-input tabular-nums" type="tel" autocomplete="off" />
				</div>
				<div class="form-field">
					<label class="field-label" for="fournisseur-contact-email">Email</label>
					<input id="fournisseur-contact-email" v-model="values.contact_email" class="field-input" type="email" autocomplete="off" :aria-invalid="Boolean(errors.contact_email)" />
					<p v-if="errors.contact_email" class="field-error" role="alert">{{ errors.contact_email }}</p>
				</div>
			</div>
		</template>

		<h3 class="form-section">Pièces administratives</h3>
		<div class="form-grid">
			<div v-for="item in PIECES" :key="item.field" class="form-field">
				<label class="field-label" :for="`fournisseur-${item.field}`">{{ item.label }}</label>
				<input :id="`fournisseur-${item.field}`" v-model="values[item.field]" class="field-input tabular-nums" autocomplete="off" />
			</div>
		</div>
		<p v-if="!editing" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Les fichiers des pièces se joignent ensuite depuis la fiche.</span></p>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer le fournisseur' }}</button>
		</template>
	</FormDialog>
</template>
