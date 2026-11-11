<script setup lang="ts">
import { computed, ref } from 'vue'
import FormDialog from '@shared/components/FormDialog.vue'
import { cloturerOrdre } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { confirmAction } from '@/lib/confirm'
import { clotureLignes, parseQty, rendementCloture, type OrdreDetail } from '@/lib/ordres'

/**
 * Clôture d'un ordre : une seule question (combien d'unités bonnes), le rendement calculé en direct, la vérification
 * des matières et ce qui va bouger dans le stock. Hors tolérance, une phrase d'explication est demandée.
 */
const props = defineProps<{ ordre: OrdreDetail; utilises: Record<string, string> }>()
const emit = defineEmits<{ close: []; closed: [ordre: OrdreDetail] }>()

const produit = ref('')
const remarque = ref('')
const saisie = ref<Record<string, string>>({ ...props.utilises })
const busy = ref(false)
const error = ref('')
const fieldError = ref('')

const quantite = computed(() => parseQty(produit.value))
const result = computed(() => rendementCloture(quantite.value, props.ordre))
const lignes = computed(() => clotureLignes(props.ordre, saisie.value))
const incoherent = computed(() => lignes.value.filter((line) => !line.ok))
const unite = computed(() => props.ordre.unite ?? '')
const pct = (value: number) => `${String(value).replace('.', ',')} %`

const rebuts = computed(() => props.ordre.rebuts.map((row) => `${formatQty(row.quantite)} ${row.designation}`).join(', '))
const consommes = computed(() =>
	props.ordre.matieres
		.map((line) => {
			const value = parseQty(saisie.value[line.name] ?? line.utilise)
			return `${formatQty(Number.isFinite(value) ? value : 0)} ${line.unite ?? ''} ${line.designation}`.replace(/\s+/g, ' ')
		})
		.join(', '),
)

async function submit() {
	if (busy.value) return
	error.value = ''
	fieldError.value = quantite.value > 0 ? '' : "Indiquez combien d'unités bonnes ont été produites."
	if (fieldError.value) return
	if (incoherent.value.length) {
		error.value = `Vérifiez les quantités : ${incoherent.value.map((line) => line.designation).join(', ')} dépasse ce qui est arrivé à l'atelier. Ajoutez un complément si nécessaire.`
		return
	}
	if (result.value.horsTolerance && !remarque.value.trim()) {
		error.value = "Le rendement est hors tolérance : expliquez l'écart en une phrase."
		return
	}
	if (!(await confirmAction({
		title: "Clôturer l'ordre",
		message: `${formatQty(quantite.value)} ${props.ordre.designation} entrent dans ${props.ordre.depots.pf ?? 'les produits finis'}. Les matières utilisées sortent de l'atelier${props.ordre.rebuts.length ? `, les rebuts partent à ${props.ordre.depots.rebuts ?? 'leur dépôt'}` : ''}.\nL'ordre passe à « Terminé » et ne se modifie plus.`,
		confirmLabel: 'Clôturer et mettre à jour le stock',
	}))) return
	busy.value = true
	try {
		const lignesSaisies = props.ordre.matieres.map((line) => ({ name: line.name, utilise: parseQty(saisie.value[line.name] ?? line.utilise) }))
		emit('closed', await cloturerOrdre(props.ordre, { qty_reelle_pf: quantite.value, lignes: lignesSaisies, remarque: remarque.value.trim() || undefined }))
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="`Clôturer ${ordre.name}`" :dirty="Boolean(produit)" :busy="busy" hint="Ctrl + Entrée pour clôturer" @close="emit('close')" @submit="submit">
		<p class="text-sm text-ink-gray-7">{{ ordre.designation }} · {{ formatQty(ordre.qty_prevue) }} {{ unite }} prévues<template v-if="ordre.lot_pf"> · lot {{ ordre.lot_pf }}</template></p>

		<div class="cloture-head">
			<div class="form-field">
				<label class="field-label" for="cloture-produit">Combien d'unités bonnes ? <span class="req">obligatoire</span></label>
				<span class="flex items-center gap-1.5"><input id="cloture-produit" v-model="produit" class="field-input cloture-qty" inputmode="decimal" :aria-invalid="Boolean(fieldError)" @input="fieldError = ''" /><span class="text-sm text-ink-gray-7">{{ unite }}</span></span>
				<p class="field-note">Seulement les unités conformes, prêtes à vendre.</p>
				<p v-if="fieldError" class="field-error" role="alert">{{ fieldError }}</p>
			</div>
			<div v-if="quantite > 0" class="cloture-yield" :class="result.horsTolerance ? 'tone-amber' : 'tone-green'" role="status">
				<span class="text-xs font-semibold">Rendement</span>
				<strong>{{ pct(result.rendement) }}</strong>
				<span class="text-sm">{{ formatQty(quantite) }} sur {{ formatQty(ordre.qty_prevue) }} prévues. Objectif {{ pct(ordre.rendement_vise) }}, écart toléré ± {{ pct(ordre.tolerance) }} : <strong>{{ result.horsTolerance ? 'hors tolérance' : 'dans la tolérance' }}</strong>.</span>
			</div>
		</div>

		<div v-if="result.horsTolerance && quantite > 0" class="form-field">
			<label class="field-label" for="cloture-remarque">Pourquoi cet écart ? <span class="req">obligatoire</span></label>
			<textarea id="cloture-remarque" v-model="remarque" class="field-input" rows="2" placeholder="Ex. bourrage de la remplisseuse, 40 flacons écartés"></textarea>
			<p class="field-note">La remarque va au fil de l'ordre ; les responsables de la production sont prévenus.</p>
		</div>

		<section class="flex flex-col gap-1.5">
			<h3 class="text-sm font-semibold">Matières : vérification</h3>
			<div class="ref-scroll"><table class="ref-table">
				<thead><tr><th>Matière</th><th class="end">Utilisé</th><th class="end">Rebut</th><th class="end">À l'atelier</th><th></th></tr></thead>
				<tbody>
					<tr v-for="line in lignes" :key="line.name">
						<td class="font-medium">{{ line.designation }}</td>
						<td class="end"><input v-model="saisie[line.name]" class="field-input w-24 text-right tabular-nums" inputmode="decimal" :aria-label="`Quantité utilisée de ${line.designation}`" /></td>
						<td class="end tabular-nums">{{ formatQty(line.rebut) }}</td>
						<td class="end tabular-nums">{{ formatQty(line.atelier) }}</td>
						<td :class="line.ok ? 'text-tone-green' : 'font-semibold text-tone-red'">{{ !line.ok ? 'dépasse' : line.reste > 0 ? `✓ ${formatQty(line.reste)} restent` : '✓ cohérent' }}</td>
					</tr>
				</tbody>
			</table></div>
		</section>

		<section class="cloture-moves" aria-label="Ce qui va se passer dans le stock">
			<h3 class="text-sm font-semibold">Ce qui va se passer dans le stock</h3>
			<p><span class="cloture-sign tone-blue" aria-hidden="true">+</span><span><strong>{{ quantite > 0 ? formatQty(quantite) : '…' }} {{ ordre.designation }}</strong> entrent dans <strong>{{ ordre.depots.pf ?? 'les produits finis' }}</strong>{{ ordre.lot_pf ? `, lot ${ordre.lot_pf}` : ', avec un nouveau lot' }}.</span></p>
			<p><span class="cloture-sign tone-orange" aria-hidden="true">−</span><span>Les matières utilisées sortent de l'atelier : {{ consommes }}.</span></p>
			<p v-if="ordre.rebuts.length"><span class="cloture-sign tone-gray" aria-hidden="true">→</span><span>Les rebuts partent au dépôt <strong>{{ ordre.depots.rebuts }}</strong> : {{ rebuts }}.</span></p>
		</section>

		<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Clôture…' : 'Clôturer et mettre à jour le stock' }}</button>
		</template>
	</FormDialog>
</template>
