<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import LucideLink from '~icons/lucide/link'
import FormDialog from '@shared/components/FormDialog.vue'
import { detacherTarif, getChangements, recalculer, setRegle } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { ARRONDIS, formatDate, formatPrix, regleTexte, type Ajustement, type Changement, type Regle, type TarifSens, type TarifsReglages } from '@/lib/tarifs'

/**
 * Tarifs et prix › un tarif calculé depuis un autre : sa règle, et les changements du tarif de base à reprendre.
 * Chaque changement se coche ; un prix modifié à la main ici est décoché d'office. Les décochés restent signalés,
 * sauf « Ignorer les autres », qui les marque vus sans changer leur prix.
 */
const props = defineProps<{ liste: string; regle: Regle; sens: TarifSens; devise: string; canEdit: boolean }>()
const emit = defineEmits<{ changed: [message: string]; detached: [reglages: TarifsReglages] }>()

const changements = ref<Changement[] | null>(null)
const coches = reactive<Record<string, boolean>>({})
const busy = ref(false)
const error = ref('')
const nbCoches = computed(() => (changements.value ?? []).filter((row) => coches[row.cle]).length)
const tiersMot = computed(() => (props.sens === 'vente' ? 'client' : 'fournisseur'))

async function load() {
	if (!props.regle.changements) {
		changements.value = []
		return
	}
	try {
		const fresh = await getChangements(props.liste)
		changements.value = fresh.changements
		for (const key of Object.keys(coches)) delete coches[key]
		for (const row of fresh.changements) coches[row.cle] = !row.manuel
		error.value = ''
	} catch (e) {
		error.value = (e as Error).message
	}
}
watch(() => [props.liste, props.regle.changements], load, { immediate: true })

function libelle(row: Changement) {
	if (row.type === 'nouveau') return 'nouveau prix dans le tarif de base'
	if (row.type === 'supprime') return 'retiré du tarif de base : ce prix sera supprimé'
	if (row.manuel) return `modifié à la main ici (${formatPrix(row.actuel)})`
	if (row.fin && row.base_avant === row.base_apres) return `s'arrête le ${formatDate(row.fin)}`
	return row.fin ? `jusqu'au ${formatDate(row.fin)}` : ''
}

async function appliquer(ignorerAutres = false) {
	if (busy.value || !changements.value) return
	const cles = changements.value.filter((row) => coches[row.cle]).map((row) => row.cle)
	const ignorer = ignorerAutres ? changements.value.filter((row) => !coches[row.cle] && row.type === 'prix').map((row) => row.cle) : []
	if (!cles.length && !ignorer.length) return
	busy.value = true
	error.value = ''
	try {
		const { touches } = await recalculer(props.liste, cles, ignorer)
		emit('changed', `${touches} prix mis à jour depuis « ${props.regle.base} ».`)
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

async function detacher() {
	if (busy.value) return
	if (!(await confirmAction({ title: 'Détacher du tarif de base', message: `Les prix de « ${props.liste} » restent tels quels, mais les changements de « ${props.regle.base} » ne seront plus signalés ni recalculés.`, confirmLabel: 'Détacher' }))) return
	busy.value = true
	try {
		emit('detached', await detacherTarif(props.liste))
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

// Modifier la règle : les prix calculés suivent, ceux modifiés à la main restent.
const edition = ref(false)
const form = reactive({ ajustement: 'remise' as Ajustement, pourcentage: '', arrondi: 0, error: '' })
function ouvrirRegle() {
	Object.assign(form, { ajustement: props.regle.ajustement, pourcentage: String(props.regle.pourcentage).replace('.', ','), arrondi: props.regle.arrondi, error: '' })
	edition.value = true
}
async function enregistrerRegle() {
	if (busy.value) return
	const pourcentage = Number(form.pourcentage.replace(',', '.')) || 0
	if (form.ajustement !== 'aucun' && (!(pourcentage > 0) || (form.ajustement === 'remise' && pourcentage >= 100))) {
		form.error = 'Saisissez un pourcentage valable.'
		return
	}
	busy.value = true
	try {
		const { gardes } = await setRegle(props.liste, { ajustement: form.ajustement, pourcentage: form.ajustement === 'aucun' ? 0 : pourcentage, arrondi: form.arrondi })
		edition.value = false
		emit('changed', gardes ? `Règle changée. ${gardes} prix modifié${gardes > 1 ? 's' : ''} à la main ${gardes > 1 ? 'restent' : 'reste'} tel${gardes > 1 ? 's' : ''} quel${gardes > 1 ? 's' : ''}.` : 'Règle changée, prix recalculés.')
	} catch (e) {
		form.error = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<div class="flex flex-col gap-3">
		<div class="flex flex-wrap items-center gap-2">
			<span class="badge tone-blue"><LucideLink class="h-3 w-3" aria-hidden="true" />Basé sur « {{ regle.base }} » · {{ regleTexte(regle) }}</span>
			<span v-if="regle.calcule_le" class="text-xs text-ink-gray-6">dernier calcul le {{ formatDate(regle.calcule_le) }}</span>
			<span class="flex-auto"></span>
			<template v-if="canEdit">
				<button type="button" class="btn-secondary btn-sm" :disabled="busy" @click="ouvrirRegle">Modifier la règle</button>
				<button type="button" class="btn-secondary btn-sm" :disabled="busy" @click="detacher">Détacher du tarif de base</button>
			</template>
		</div>
		<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>

		<div v-if="changements?.length" class="tarifs-bandeau tone-blue flex-col items-stretch">
			<div class="flex flex-wrap items-center gap-2">
				<span class="flex-auto"><b>{{ changements.length }} changement{{ changements.length > 1 ? 's' : '' }}</b> dans « {{ regle.base }} » depuis le dernier calcul. Cochez ceux à reprendre avec la règle de ce tarif.</span>
				<template v-if="canEdit">
					<button v-if="nbCoches < changements.length" type="button" class="btn-secondary btn-sm" :disabled="busy" @click="appliquer(true)">Reprendre la sélection et ignorer les autres</button>
					<button type="button" class="btn-primary btn-sm" :disabled="busy || !nbCoches" @click="appliquer()">Reprendre {{ nbCoches }} changement{{ nbCoches > 1 ? 's' : '' }}</button>
				</template>
			</div>
			<div class="tarifs-sous overflow-x-auto">
				<table class="ref-table tarifs-sous-table">
					<thead>
						<tr>
							<th v-if="canEdit"><span class="sr-only">Reprendre</span></th>
							<th>Article</th>
							<th class="end">Tarif de base</th>
							<th class="end">Prix actuel ici</th>
							<th class="end">Après calcul</th>
							<th>Remarque</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in changements" :key="row.cle">
							<td v-if="canEdit"><input v-model="coches[row.cle]" type="checkbox" :aria-label="`Reprendre ${row.designation}`" /></td>
							<td>
								<span class="font-medium text-ink-gray-9">{{ row.designation }}</span>
								<small v-if="row.tiers" class="block text-ink-gray-6">{{ tiersMot }} : {{ row.tiers }}</small>
							</td>
							<td class="end whitespace-nowrap tabular-nums">
								<template v-if="row.type === 'prix' && row.base_avant !== row.base_apres">{{ formatPrix(row.base_avant) }} → <b class="text-ink-gray-9">{{ formatPrix(row.base_apres) }}</b></template>
								<template v-else>{{ formatPrix(row.base_apres ?? row.base_avant) || '—' }}</template>
							</td>
							<td class="end tabular-nums">{{ formatPrix(row.actuel) || '—' }}</td>
							<td class="end font-semibold tabular-nums">{{ row.type === 'supprime' ? '—' : formatPrix(row.nouveau) }}</td>
							<td><span :class="row.manuel ? 'badge tone-amber' : 'text-sm text-ink-gray-6'">{{ libelle(row) || '—' }}</span></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<FormDialog v-if="edition" title="Règle du tarif" :dirty="true" :busy="busy" hint="Ctrl + Entrée pour enregistrer" @close="edition = false" @submit="enregistrerRegle">
			<p class="text-sm text-ink-gray-6">Les prix de « {{ liste }} » sont calculés depuis « {{ regle.base }} ». Les prix modifiés à la main ne changent pas.</p>
			<div class="form-grid">
				<div class="form-field">
					<span id="regle-ajust" class="field-label">Ajustement</span>
					<div class="flex items-center gap-2">
						<div class="seg" role="group" aria-labelledby="regle-ajust">
							<button type="button" :aria-pressed="form.ajustement === 'remise'" @click="form.ajustement = 'remise'">Remise</button>
							<button type="button" :aria-pressed="form.ajustement === 'majoration'" @click="form.ajustement = 'majoration'">Majoration</button>
							<button type="button" :aria-pressed="form.ajustement === 'aucun'" @click="form.ajustement = 'aucun'">Aucun</button>
						</div>
						<label v-if="form.ajustement !== 'aucun'" class="tarif-pct">
							<input v-model="form.pourcentage" class="field-input end tabular-nums" inputmode="decimal" aria-label="Pourcentage" @input="form.error = ''" />
							<span aria-hidden="true">%</span>
						</label>
					</div>
				</div>
				<div class="form-field">
					<label class="field-label" for="regle-arrondi">Arrondir les prix</label>
					<select id="regle-arrondi" v-model.number="form.arrondi" class="field-input">
						<option v-for="item in ARRONDIS" :key="item.pas" :value="item.pas">{{ item.label }}</option>
					</select>
				</div>
			</div>
			<p v-if="form.error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ form.error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="enregistrerRegle">{{ busy ? 'Enregistrement…' : 'Recalculer les prix' }}</button>
			</template>
		</FormDialog>
	</div>
</template>
