<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormDialog from '@shared/components/FormDialog.vue'
import { createTarif, getPrix } from '@/lib/api'
import { ARRONDIS, calculerPrix, formatPrix, regleTexte, type Ajustement, type PrixResponse, type Tarif, type TarifSens, type TarifsReglages } from '@/lib/tarifs'

/**
 * Tarifs et prix › Nouveau tarif : vide, ou calculé depuis un autre tarif (remise ou majoration, arrondi).
 * L'aperçu reprend quelques prix du tarif de base avec le même calcul que le serveur.
 * Avec « Garder le lien », le tarif signale ensuite les changements de son tarif de base.
 */
const props = defineProps<{ tarifs: Tarif[]; sens: TarifSens; base?: string | null; aujourdhui: string }>()
const emit = defineEmits<{ close: []; created: [nom: string, reglages: TarifsReglages & { crees: number }] }>()

const form = reactive({
	nom: '',
	sens: props.sens,
	copie: Boolean(props.base),
	base: props.base ?? props.tarifs.find((row) => row.actif && row.sens === props.sens && row.defaut)?.name ?? props.tarifs[0]?.name ?? '',
	ajustement: 'remise' as Ajustement,
	pourcentage: '10',
	arrondi: 1,
	debut: props.aujourdhui,
	aVenir: true,
	tiers: false,
	lien: true,
})
const busy = ref(false)
const error = ref('')
const dirty = computed(() => Boolean(form.nom.trim()))
const pourcentage = computed(() => Number(form.pourcentage.replace(',', '.')) || 0)
const baseTarif = computed(() => props.tarifs.find((row) => row.name === form.base) ?? null)
const regle = computed(() => ({ ajustement: form.ajustement, pourcentage: form.ajustement === 'aucun' ? 0 : pourcentage.value, arrondi: form.arrondi }))

// Aperçu : quelques prix en vigueur du tarif de base, et ses compteurs.
const apercu = ref<PrixResponse | null>(null)
let requestId = 0
async function loadApercu() {
	if (!form.copie || !form.base) return
	const id = ++requestId
	try {
		const fresh = await getPrix(form.base, { vue: 'avec_prix', date: form.debut || props.aujourdhui })
		if (id === requestId) apercu.value = fresh
	} catch {
		if (id === requestId) apercu.value = null
	}
}
watch(() => [form.copie, form.base, form.debut], loadApercu, { immediate: true })
const exemples = computed(() => (apercu.value?.lignes ?? []).filter((ligne) => ligne.prix !== null).slice(0, 4))
const nbPrix = computed(() => apercu.value?.compte.avec_prix ?? 0)
const nbSansPrix = computed(() => apercu.value?.compte.sans_prix ?? 0)
const nbAVenir = computed(() => apercu.value?.compte.a_venir ?? 0)

async function submit() {
	if (busy.value) return
	const nom = form.nom.trim()
	if (!nom) {
		error.value = 'Donnez un nom au tarif.'
		return
	}
	if (form.copie && form.ajustement !== 'aucun' && (!(pourcentage.value > 0) || (form.ajustement === 'remise' && pourcentage.value >= 100))) {
		error.value = form.ajustement === 'remise' ? 'Saisissez une remise entre 0 et 100 %.' : 'Saisissez un pourcentage de majoration.'
		return
	}
	busy.value = true
	error.value = ''
	try {
		const copie = form.copie
			? { base: form.base, ...regle.value, debut: form.debut || props.aujourdhui, a_venir: form.aVenir ? 1 : 0, tiers: form.tiers ? 1 : 0, lien: form.lien ? 1 : 0 } as const
			: null
		emit('created', nom, await createTarif(nom, form.sens, copie))
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog title="Nouveau tarif" :dirty="dirty" :busy="busy" @close="emit('close')" @submit="submit">
		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="tarif-nom">Nom du tarif <span class="req">obligatoire</span></label>
				<input id="tarif-nom" v-model="form.nom" class="field-input" placeholder="Ex. Tarif remise 10 %" autocomplete="off" @input="error = ''" />
			</div>
			<fieldset class="form-field">
				<legend class="field-label">Pour</legend>
				<div class="flex gap-4 text-sm">
					<label class="flex items-center gap-1.5"><input v-model="form.sens" type="radio" value="vente" /> les ventes</label>
					<label class="flex items-center gap-1.5"><input v-model="form.sens" type="radio" value="achat" /> les achats</label>
				</div>
			</fieldset>
		</div>

		<fieldset class="form-field">
			<legend class="field-label">Partir de</legend>
			<div class="tarif-source-choix">
				<button type="button" class="tarif-source" :aria-pressed="!form.copie" @click="form.copie = false">
					<span class="font-semibold">Un tarif vide</span>
					<span class="text-sm text-ink-gray-6">Vous saisirez les prix un à un.</span>
				</button>
				<button type="button" class="tarif-source" :aria-pressed="form.copie" :disabled="!tarifs.length" @click="form.copie = true">
					<span class="font-semibold">Les prix d'un autre tarif</span>
					<span class="text-sm text-ink-gray-6">Copiés, avec une remise ou une majoration.</span>
				</button>
			</div>
		</fieldset>

		<div v-if="form.copie" class="prix-clore">
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="tarif-base">Tarif de base</label>
					<select id="tarif-base" v-model="form.base" class="field-input">
						<option v-for="row in tarifs" :key="row.name" :value="row.name">{{ row.name }} — {{ row.prix }} prix{{ row.actif ? '' : ' (désactivé)' }}</option>
					</select>
				</div>
				<div class="form-field">
					<span id="tarif-ajust" class="field-label">Ajustement</span>
					<div class="flex items-center gap-2">
						<div class="seg" role="group" aria-labelledby="tarif-ajust">
							<button type="button" :aria-pressed="form.ajustement === 'remise'" @click="form.ajustement = 'remise'">Remise</button>
							<button type="button" :aria-pressed="form.ajustement === 'majoration'" @click="form.ajustement = 'majoration'">Majoration</button>
							<button type="button" :aria-pressed="form.ajustement === 'aucun'" @click="form.ajustement = 'aucun'">Aucun</button>
						</div>
						<label v-if="form.ajustement !== 'aucun'" class="tarif-pct">
							<input v-model="form.pourcentage" class="field-input end tabular-nums" inputmode="decimal" aria-label="Pourcentage" @input="error = ''" />
							<span aria-hidden="true">%</span>
						</label>
					</div>
				</div>
				<div class="form-field">
					<label class="field-label" for="tarif-arrondi">Arrondir les prix</label>
					<select id="tarif-arrondi" v-model.number="form.arrondi" class="field-input">
						<option v-for="item in ARRONDIS" :key="item.pas" :value="item.pas">{{ item.label }}</option>
					</select>
				</div>
				<div class="form-field">
					<label class="field-label" for="tarif-debut">Valable à partir du</label>
					<input id="tarif-debut" v-model="form.debut" class="field-input" type="date" />
				</div>
			</div>

			<fieldset class="form-field">
				<legend class="field-label">Prix repris</legend>
				<div class="flex flex-col gap-1.5 text-sm">
					<label class="flex items-center gap-1.5"><input type="checkbox" checked disabled /> les prix en vigueur à cette date <span class="text-ink-gray-6">({{ nbPrix }})</span></label>
					<label class="flex items-center gap-1.5"><input v-model="form.aVenir" type="checkbox" /> les prix à venir, avec leurs dates <span v-if="nbAVenir" class="text-ink-gray-6">({{ nbAVenir }} articles)</span></label>
					<label v-if="baseTarif?.sens === form.sens" class="flex items-center gap-1.5"><input v-model="form.tiers" type="checkbox" /> les prix réservés à un {{ form.sens === 'vente' ? 'client' : 'fournisseur' }}</label>
				</div>
			</fieldset>

			<label class="flex items-start gap-2">
				<input v-model="form.lien" type="checkbox" class="mt-0.5 flex-none" />
				<span class="min-w-0 flex-1">
					<span class="font-medium">Garder le lien avec le tarif de base</span>
					<span class="block text-sm text-ink-gray-6">Quand un prix change dans « {{ form.base }} », ce tarif le signale et propose de le recalculer avec la même règle. Les prix modifiés à la main ne sont jamais écrasés sans votre accord.</span>
				</span>
			</label>

			<div class="flex flex-col gap-1.5">
				<span class="field-label">Aperçu</span>
				<p v-if="!apercu" class="text-sm text-ink-gray-6">Chargement…</p>
				<p v-else-if="!exemples.length" class="text-sm text-ink-gray-6">Ce tarif n'a aucun prix en vigueur à cette date.</p>
				<div v-else class="tarifs-sous">
					<table class="ref-table tarifs-sous-table">
						<thead>
							<tr><th>Article</th><th class="end">Tarif de base</th><th class="end">Nouveau prix</th></tr>
						</thead>
						<tbody>
							<tr v-for="ligne in exemples" :key="ligne.article">
								<td>{{ ligne.designation }}</td>
								<td class="end tabular-nums">{{ formatPrix(ligne.prix) }}</td>
								<td class="end font-semibold tabular-nums">{{ formatPrix(calculerPrix(ligne.prix ?? 0, regle.ajustement, regle.pourcentage, regle.arrondi)) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-if="apercu" class="field-note">{{ nbPrix }} prix, {{ regleTexte(regle) }}.<template v-if="nbSansPrix"> {{ nbSansPrix }} article{{ nbSansPrix > 1 ? 's' : '' }} sans prix dans le tarif de base resteront sans prix.</template></p>
			</div>
		</div>
		<p v-else class="field-note">Le tarif est créé vide et actif, dans la devise de la société. Vous y saisirez ensuite les prix.</p>
		<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Création…' : form.copie ? `Créer le tarif et ses ${nbPrix} prix` : 'Créer le tarif' }}</button>
		</template>
	</FormDialog>
</template>
