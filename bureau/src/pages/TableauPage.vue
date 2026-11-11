<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideRefreshCw from '~icons/lucide/refresh-cw'
import { closeRealtime, connectRealtime, isForeignChange, throttledReload, type RealtimeEvent } from '@shared/realtime'
import BarChart from '@/components/BarChart.vue'
import BureauShell from '@/components/BureauShell.vue'
import { getTableau } from '@/lib/api'
import { amount, ficheRoute, valueText, indicateurValue, lienRoute, MODULE_LABELS, PERIODES, SERIES_COLORS, type PeriodeKey, type Tableau, type TableauModule } from '@/lib/tableaux'

/**
 * Tableau de bord d'un module : quatre indicateurs (chacun ouvre sa liste filtrée), deux graphiques,
 * et « À traiter » : les listes courtes de ce qui attend une action. Se recharge quand une pièce change ailleurs.
 */
const props = defineProps<{ module: TableauModule }>()
const route = useRoute()
const router = useRouter()

const periode = computed<PeriodeKey>(() => {
	const value = route.query.periode
	return PERIODES.some((item) => item.key === value) ? (value as PeriodeKey) : 'mois'
})
function choosePeriode(key: PeriodeKey) {
	router.replace({ query: key === 'mois' ? {} : { periode: key } })
}

const tableau = ref<Tableau | null>(null)
const error = ref('')
const loading = ref(false)
let lastRequest = 0
async function load() {
	const request = ++lastRequest
	loading.value = true
	error.value = ''
	try {
		const response = await getTableau(props.module, periode.value)
		if (request === lastRequest) tableau.value = response
	} catch (e) {
		// Rechargement en arrière-plan raté : on garde ce qui est affiché.
		if (request === lastRequest && !tableau.value) error.value = (e as Error).message
	} finally {
		if (request === lastRequest) loading.value = false
	}
}
watch(
	() => props.module,
	() => {
		tableau.value = null
		load()
	},
	{ immediate: true },
)
watch(periode, load)

const reload = throttledReload(load)
onMounted(() => {
	connectRealtime<RealtimeEvent>(
		'unicare_bureau_update',
		(event) => {
			if (isForeignChange(event, window.user)) reload()
		},
		load,
	)
})
onBeforeUnmount(closeRealtime)

const label = computed(() => MODULE_LABELS[props.module])
const subtitle = computed(() => {
	if (!tableau.value) return ''
	const day = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(tableau.value.jour))
	return tableau.value.sans_periode ? `Au ${day}` : `${tableau.value.periode.libelle} · au ${day}`
})
const repartitionMax = computed(() => Math.max(1, ...(tableau.value?.repartition?.lignes.map((ligne) => ligne.valeur) ?? [])))
const echeancierMax = computed(() => Math.max(1, ...(tableau.value?.echeancier?.lignes.flatMap((ligne) => ligne.valeurs) ?? [])))
const percent = (value: number, max: number) => `${Math.max(value > 0 ? 2 : 0, (value / max) * 100)}%`
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Tableau de bord' }]" :active="`tableau-${module}`">
		<div class="bureau-work tdb">
			<div class="tdb-head">
				<div class="min-w-0">
					<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">{{ label }}</h1>
					<p class="text-sm text-ink-gray-6">
						{{ subtitle }}<span v-if="tableau"> · à jour en temps réel</span>
					</p>
				</div>
				<LucideRefreshCw v-if="loading && tableau" class="h-4 w-4 animate-spin text-ink-gray-5" aria-label="Mise à jour" />
				<span class="flex-1"></span>
				<div v-if="!tableau?.sans_periode" class="tdb-periods" role="group" aria-label="Période des indicateurs et des graphiques">
					<button v-for="item in PERIODES" :key="item.key" type="button" class="tdb-period" :aria-pressed="periode === item.key" @click="choosePeriode(item.key)">{{ item.label }}</button>
				</div>
			</div>

			<p v-if="error" class="card p-4 tdb-ink-red">{{ error }}</p>
			<p v-else-if="!tableau" class="card p-4 text-ink-gray-6">Chargement du tableau de bord…</p>

			<template v-else>
				<section v-if="tableau.indicateurs.length" class="tdb-kpis" aria-label="Indicateurs">
					<RouterLink v-for="kpi in tableau.indicateurs" :key="kpi.key" :to="lienRoute(kpi.lien)" class="card tdb-kpi">
						<span class="text-sm font-medium text-ink-gray-7">{{ kpi.label }}</span>
						<span class="tdb-kpi-value" :class="kpi.ton === 'red' && 'tdb-ink-red'">{{ indicateurValue(kpi) }}</span>
						<span class="text-xs text-ink-gray-6">
							<template v-for="(detail, index) in kpi.details" :key="index">
								<span :class="[detail.fort && 'font-semibold', detail.ton && `tdb-ink-${detail.ton}`]">{{ detail.texte }}</span>{{ index < kpi.details.length - 1 ? ' ' : '' }}
							</template>
						</span>
					</RouterLink>
				</section>

				<section v-if="tableau.tendance || tableau.repartition || tableau.echeancier" class="tdb-charts" aria-label="Graphiques">
					<div v-if="tableau.tendance" class="card tdb-card">
						<h2 class="tdb-card-title">{{ tableau.tendance.titre }}</h2>
						<BarChart :tendance="tableau.tendance" />
						<p v-if="tableau.tendance.note" class="text-xs text-ink-gray-6">{{ tableau.tendance.note }}</p>
					</div>

					<div v-if="tableau.repartition" class="card tdb-card">
						<div class="flex items-baseline gap-2">
							<h2 class="tdb-card-title">{{ tableau.repartition.titre }}</h2>
							<span v-if="tableau.repartition.sous_titre" class="ml-auto text-xs text-ink-gray-6">{{ tableau.repartition.sous_titre }}</span>
						</div>
						<ol v-if="tableau.repartition.lignes.length" class="tdb-hbars">
							<li v-for="ligne in tableau.repartition.lignes" :key="ligne.name">
								<div class="flex justify-between gap-3 text-sm">
									<RouterLink :to="ficheRoute(ligne.fiche, ligne.name)" class="truncate font-medium text-link">{{ ligne.label }}</RouterLink>
									<span class="flex-none font-medium tabular-nums text-ink-gray-9">{{ valueText(ligne.valeur, tableau.repartition.unite) }}</span>
								</div>
								<div class="tdb-track"><div class="tdb-fill" :style="{ width: percent(ligne.valeur, repartitionMax), background: SERIES_COLORS[0] }"></div></div>
							</li>
						</ol>
						<p v-else class="py-6 text-center text-sm text-ink-gray-6">{{ tableau.repartition.vide }}</p>
						<p v-if="tableau.repartition.note && tableau.repartition.lignes.length" class="mt-auto text-xs text-ink-gray-6">{{ tableau.repartition.note }}</p>
					</div>

					<div v-if="tableau.echeancier" class="card tdb-card">
						<h2 class="tdb-card-title">{{ tableau.echeancier.titre }}</h2>
						<div v-if="tableau.echeancier.series.length > 1" class="chart-legend">
							<span v-for="(serie, index) in tableau.echeancier.series" :key="serie.key" class="chart-legend-item">
								<span class="chart-swatch" :style="{ background: SERIES_COLORS[index] }" aria-hidden="true"></span>{{ serie.label }}
							</span>
						</div>
						<ol class="tdb-hbars">
							<li v-for="ligne in tableau.echeancier.lignes" :key="ligne.label">
								<p class="text-sm font-medium text-ink-gray-9">{{ ligne.label }}</p>
								<div v-for="(value, index) in ligne.valeurs" :key="index" class="flex items-center gap-2">
									<div class="flex-1"><div class="tdb-fill" :style="{ width: percent(value, echeancierMax), background: SERIES_COLORS[index] }"></div></div>
									<span class="w-28 flex-none text-right text-sm tabular-nums text-ink-gray-8">
										<span class="sr-only">{{ tableau.echeancier.series[index]?.label }} : </span>{{ amount(value) }}
									</span>
								</div>
							</li>
						</ol>
						<p v-if="tableau.echeancier.note" class="mt-auto text-xs text-ink-gray-6">{{ tableau.echeancier.note }}</p>
					</div>
				</section>

				<section v-if="tableau.listes.length" aria-labelledby="a-traiter" class="flex flex-col gap-2.5">
					<h2 id="a-traiter" class="text-base font-semibold text-ink-gray-9">À traiter</h2>
					<div class="tdb-lists">
						<div v-for="liste in tableau.listes" :key="liste.key" class="card tdb-list">
							<div class="tdb-list-head">
								<h3 class="tdb-card-title">{{ liste.titre }}</h3>
								<span class="badge" :class="`tone-${liste.ton || 'gray'}`">{{ liste.total }}</span>
								<RouterLink :to="lienRoute(liste.lien)" class="ml-auto text-sm font-medium text-link">Tout voir</RouterLink>
							</div>
							<RouterLink v-for="ligne in liste.lignes" :key="ligne.name" :to="ficheRoute(ligne.fiche, ligne.name)" class="tdb-row">
								<span v-if="ligne.nature" class="badge tone-blue tdb-nature">{{ ligne.nature }}</span>
								<span class="tdb-ref" :class="ligne.titre === ligne.name && 'tabular-nums'">{{ ligne.titre }}</span>
								<span class="min-w-0 flex-1 truncate text-ink-gray-7">{{ ligne.detail }}</span>
								<span v-if="ligne.badge" class="badge flex-none" :class="`tone-${ligne.badge.ton || 'gray'}`">{{ ligne.badge.texte }}</span>
								<span v-if="ligne.montant != null" class="tdb-amount">{{ amount(ligne.montant) }}</span>
							</RouterLink>
							<p v-if="!liste.lignes.length" class="tdb-empty">Rien à traiter.</p>
						</div>
					</div>
				</section>
			</template>
		</div>
	</BureauShell>
</template>
