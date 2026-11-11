<script setup lang="ts">
import { reactive, ref } from 'vue'
import LucideMail from '~icons/lucide/mail'
import LucidePencil from '~icons/lucide/pencil'
import LucidePhone from '~icons/lucide/phone'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import { deleteContact, saveContact, type ContactValues } from '@/lib/api'
import type { ClientContact } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'

/**
 * Contacts d'un client ou d'un fournisseur : liste, ajout, modification et retrait, sans passer par le Desk.
 * Un contact saisi seulement sur la fiche du tiers (sans document Contact) se modifie avec la fiche elle-même.
 */
const props = defineProps<{ contacts: ClientContact[]; linkDoctype: 'Customer' | 'Supplier'; linkName: string; canEdit: boolean }>()
const emit = defineEmits<{ changed: [message: string] }>()

const editing = ref<{ contact: string | null } | null>(null)
const form = reactive<ContactValues>({ prenom: '', nom: '', fonction: '', telephone: '', email: '', principal: false })
const error = ref('')
const busy = ref(false)

function open(contact?: ClientContact) {
	error.value = ''
	Object.assign(form, {
		prenom: contact?.prenom ?? (contact && !contact.name ? contact.nom ?? '' : ''),
		nom: contact?.nom_famille ?? '',
		fonction: contact?.fonction ?? '',
		telephone: contact?.telephone ?? '',
		email: contact?.email ?? '',
		principal: Boolean(contact?.principal) || !props.contacts.length,
	})
	editing.value = { contact: contact?.name ?? null }
}
async function submit() {
	if (busy.value || !editing.value) return
	error.value = form.prenom.trim() || form.nom.trim() ? '' : 'Indiquez au moins le prénom ou le nom.'
	if (error.value) return
	busy.value = true
	try {
		await saveContact(props.linkDoctype, props.linkName, editing.value.contact, form)
		emit('changed', editing.value.contact ? 'Contact enregistré.' : 'Contact ajouté.')
		editing.value = null
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
async function remove(contact: ClientContact) {
	if (!contact.name) return
	if (!(await confirmAction({ title: 'Retirer le contact', message: `${contact.nom || 'Ce contact'} ne sera plus un contact de cette fiche.`, confirmLabel: 'Retirer', danger: true }))) return
	try {
		await deleteContact(props.linkDoctype, props.linkName, contact.name)
		emit('changed', 'Contact retiré.')
	} catch (e) {
		error.value = (e as Error).message
	}
}
</script>

<template>
	<section class="card ref-card">
		<div class="ref-card-head">
			<h3>Contacts</h3>
			<button v-if="canEdit" type="button" class="btn-secondary" @click="open()"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter</button>
		</div>
		<p v-if="!contacts.length" class="text-ink-gray-6">Aucun contact enregistré.</p>
		<div v-for="(contact, index) in contacts" :key="contact.name ?? index" class="contact">
			<p class="flex items-baseline gap-1.5">
				<span class="font-semibold text-ink-gray-9">{{ contact.nom || 'Sans nom' }}</span>
				<span v-if="contact.principal" class="text-sm text-ink-gray-6">Principal</span>
				<span class="flex-auto"></span>
				<template v-if="canEdit && contact.name">
					<button type="button" class="icon-btn" :aria-label="`Modifier ${contact.nom || 'le contact'}`" @click="open(contact)"><LucidePencil class="h-3.5 w-3.5" aria-hidden="true" /></button>
					<button type="button" class="icon-btn" :aria-label="`Retirer ${contact.nom || 'le contact'}`" @click="remove(contact)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
				</template>
			</p>
			<p v-if="contact.fonction" class="text-sm text-ink-gray-6">{{ contact.fonction }}</p>
			<p class="contact-links">
				<a v-if="contact.telephone" class="ref-link tabular-nums" :href="`tel:${contact.telephone}`"><LucidePhone class="h-3.5 w-3.5" aria-hidden="true" />{{ contact.telephone }}</a>
				<a v-if="contact.email" class="ref-link" :href="`mailto:${contact.email}`"><LucideMail class="h-3.5 w-3.5" aria-hidden="true" />{{ contact.email }}</a>
			</p>
			<p v-if="canEdit && !contact.name" class="text-xs text-ink-gray-6">Saisi sur la fiche : il se modifie avec « Modifier ».</p>
		</div>
		<p v-if="error && !editing" role="alert" class="text-sm text-tone-red">{{ error }}</p>

		<FormDialog v-if="editing" :title="editing.contact ? 'Modifier le contact' : 'Nouveau contact'" :dirty="Boolean(form.prenom || form.nom)" :busy="busy" hint="Ctrl + Entrée pour enregistrer" @close="editing = null" @submit="submit">
			<div class="form-grid">
				<div class="form-field"><label class="field-label" for="contact-prenom">Prénom</label><input id="contact-prenom" v-model="form.prenom" class="field-input" autocomplete="off" /></div>
				<div class="form-field"><label class="field-label" for="contact-nom">Nom</label><input id="contact-nom" v-model="form.nom" class="field-input" autocomplete="off" /></div>
				<div class="form-field"><label class="field-label" for="contact-fonction">Fonction</label><input id="contact-fonction" v-model="form.fonction" class="field-input" autocomplete="off" /></div>
				<div class="form-field"><label class="field-label" for="contact-telephone">Téléphone</label><input id="contact-telephone" v-model="form.telephone" class="field-input tabular-nums" type="tel" autocomplete="off" /></div>
				<div class="form-field"><label class="field-label" for="contact-email">E-mail</label><input id="contact-email" v-model="form.email" class="field-input" type="email" autocomplete="off" /></div>
			</div>
			<label class="flex items-center gap-2 text-sm"><input v-model="form.principal" type="checkbox" /> Contact principal</label>
			<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="submit">Enregistrer</button>
			</template>
		</FormDialog>
	</section>
</template>
