<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import FormDialog from '@shared/components/FormDialog.vue'
import LinkInput from '@/components/LinkInput.vue'
import { saveLigne } from '@/lib/api'
import { formatDate, formatPeriode, formatPrix, parsePrix, veille, type LignePrix, type LignesArticle, type LigneValeurs } from '@/lib/tarifs'

/**
 * Tarifs et prix › un prix d'un article : nouveau (à partir d'une date, ou réservé à un client / fournisseur) ou modifié.
 * Un nouveau prix général propose d'arrêter la veille le prix de même unité encore ouvert à sa date de début.
 */
const props = defineProps<{ liste: string; detail: LignesArticle; ligne?: LignePrix | null; pourTiers?: boolean; aujourdhui: string }>()
const emit = defineEmits<{ close: []; saved: [detail: LignesArticle] }>()

const achat = computed(() => props.detail.sens === 'achat')
const tiersLabel = computed(() => (achat.value ? 'fournisseur' : 'client'))
const edition = computed(() => Boolean(props.ligne))

const valeurs = reactive<LigneValeurs>({
	prix: props.ligne ? formatPrix(props.ligne.prix) : '',
	debut: props.ligne?.debut ?? props.aujourdhui,
	fin: props.ligne?.fin ?? '',
	unite: props.ligne?.unite ?? props.detail.unite,
	tiers: props.ligne?.tiers ?? '',
	note: props.ligne?.note ?? '',
	delai: props.ligne?.delai ? String(props.ligne.delai) : '',
})
const pour = ref<'tous' | 'tiers'>(props.ligne?.tiers || props.pourTiers ? 'tiers' : 'tous')
const clore = ref(!edition.value)
const busy = ref(false)
const error = ref('')
const initial = JSON.stringify(valeurs)
const dirty = computed(() => JSON.stringify(valeurs) !== initial)

/** Le prix de même portée encore ouvert à la date de début : celui que « Clore » arrêtera. */
const remplace = computed(() => {
	if (!valeurs.debut) return null
	const tiers = pour.value === 'tiers' ? valeurs.tiers || null : null
	return (
		props.detail.lignes.find(
			(row) =>
				row.ligne !== props.ligne?.ligne &&
				!row.lot &&
				row.tiers === tiers &&
				row.unite === valeurs.unite &&
				(!row.debut || row.debut < valeurs.debut) &&
				(!row.fin || row.fin >= valeurs.debut),
		) ?? null
	)
})

async function submit() {
	if (busy.value) return
	const parsed = parsePrix(valeurs.prix)
	if ('error' in parsed || parsed.value === null) {
		error.value = 'error' in parsed ? parsed.error : 'Saisissez le prix.'
		return
	}
	if (!valeurs.debut) {
		error.value = 'Indiquez à partir de quand le prix est valable.'
		return
	}
	if (valeurs.fin && valeurs.fin < valeurs.debut) {
		error.value = 'La fin de validité ne peut pas précéder son début.'
		return
	}
	if (pour.value === 'tiers' && !valeurs.tiers) {
		error.value = `Choisissez le ${tiersLabel.value}.`
		return
	}
	busy.value = true
	error.value = ''
	try {
		const payload = { ...valeurs, tiers: pour.value === 'tiers' ? valeurs.tiers : '' }
		const ligne = props.ligne ? { ligne: props.ligne.ligne, modified: props.ligne.modified } : null
		emit('saved', await saveLigne(props.liste, props.detail.article, payload, ligne, clore.value && Boolean(remplace.value)))
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="edition ? 'Modifier le prix' : 'Nouveau prix'" :dirty="dirty" :busy="busy" hint="Ctrl + Entrée pour enregistrer" @close="emit('close')" @submit="submit">
		<p class="text-sm text-ink-gray-6">{{ detail.designation }} · {{ detail.article }} · {{ liste }}</p>
		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="prix-montant">Prix HT ({{ detail.devise }}) <span class="req">obligatoire</span></label>
				<input id="prix-montant" v-model="valeurs.prix" class="field-input end tabular-nums" inputmode="decimal" autocomplete="off" @input="error = ''" />
			</div>
			<div class="form-field">
				<label class="field-label" for="prix-unite">Unité</label>
				<select id="prix-unite" v-model="valeurs.unite" class="field-input">
					<option v-for="unite in detail.unites" :key="unite" :value="unite">{{ unite }}{{ unite === detail.unite ? ' (unité de stock)' : '' }}</option>
				</select>
			</div>
			<div class="form-field">
				<label class="field-label" for="prix-debut">Valable à partir du <span class="req">obligatoire</span></label>
				<input id="prix-debut" v-model="valeurs.debut" class="field-input" type="date" @input="error = ''" />
			</div>
			<div class="form-field">
				<label class="field-label" for="prix-fin">Jusqu'au</label>
				<input id="prix-fin" v-model="valeurs.fin" class="field-input" type="date" :min="valeurs.debut || undefined" aria-describedby="prix-fin-note" @input="error = ''" />
				<p id="prix-fin-note" class="field-note">Laissez vide : le prix reste valable jusqu'au suivant.</p>
			</div>
		</div>

		<fieldset class="form-field">
			<legend class="field-label">Pour</legend>
			<div class="flex flex-wrap gap-4 text-sm">
				<label class="flex items-center gap-1.5"><input v-model="pour" type="radio" value="tous" /> tous les {{ tiersLabel }}s</label>
				<label class="flex items-center gap-1.5"><input v-model="pour" type="radio" value="tiers" /> un {{ tiersLabel }} précis</label>
			</div>
		</fieldset>
		<div v-if="pour === 'tiers'" class="form-grid">
			<div class="form-field">
				<label class="field-label" for="prix-tiers">{{ achat ? 'Fournisseur' : 'Client' }}</label>
				<LinkInput v-model="valeurs.tiers" :doctype="achat ? 'Purchase Order' : 'Sales Order'" :fieldname="achat ? 'supplier' : 'customer'" input-id="prix-tiers" />
			</div>
			<div v-if="achat" class="form-field">
				<label class="field-label" for="prix-delai">Délai de livraison (jours)</label>
				<input id="prix-delai" v-model="valeurs.delai" class="field-input end tabular-nums" inputmode="numeric" autocomplete="off" />
			</div>
		</div>
		<div v-else-if="achat" class="form-grid">
			<div class="form-field">
				<label class="field-label" for="prix-delai">Délai de livraison (jours)</label>
				<input id="prix-delai" v-model="valeurs.delai" class="field-input end tabular-nums" inputmode="numeric" autocomplete="off" />
			</div>
		</div>

		<div class="form-field">
			<label class="field-label" for="prix-note">Note</label>
			<input id="prix-note" v-model="valeurs.note" class="field-input" :placeholder="achat ? 'Ex. nouvelle grille fournisseur' : 'Ex. hausse fournisseur, contrat annuel'" autocomplete="off" />
		</div>

		<div v-if="remplace" class="prix-clore">
			<label class="flex items-start gap-2">
				<input v-model="clore" type="checkbox" class="mt-0.5" />
				<span>
					<span class="font-medium">Arrêter le prix actuel la veille</span>
					<span class="block text-sm text-ink-gray-6">{{ formatPrix(remplace.prix) }} {{ detail.devise }} ({{ formatPeriode(remplace.debut, remplace.fin) }}) s'arrêtera le {{ formatDate(veille(valeurs.debut)) }}.</span>
				</span>
			</label>
			<p v-if="!clore" class="rounded-control tone-amber px-3 py-2 text-sm">Sans arrêt, les deux prix seront valables en même temps : les pièces prendront le plus récent, mais l'historique sera moins lisible.</p>
		</div>
		<p v-if="pour === 'tiers'" class="field-note">Ce prix ne s'applique qu'aux pièces de ce {{ tiersLabel }}. Les autres gardent le prix général.</p>
		<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : 'Enregistrer le prix' }}</button>
		</template>
	</FormDialog>
</template>
