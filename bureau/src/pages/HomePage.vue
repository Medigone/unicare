<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideAtSign from '~icons/lucide/at-sign'
import LucideBell from '~icons/lucide/bell'
import { closeRealtime, connectRealtime, isForeignChange, throttledReload, type RealtimeEvent } from '@shared/realtime'
import BureauShell from '@/components/BureauShell.vue'
import CreateMenu from '@/components/CreateMenu.vue'
import { getAccueil, marquerNotificationsLues } from '@/lib/api'
import { ficheIcon, MODULE_TONES, quandText, resumeJournee, type AFaire, type Accueil } from '@/lib/accueil'
import { activePoste } from '@/lib/postes'
import { indicateurValue } from '@/lib/tableaux'

/**
 * Accueil : la journée de la personne connectée. Le bouton « Créer », ce qu'il y a à faire aujourd'hui (tous modules,
 * en retard, aujourd'hui, à valider), ce qui lui est adressé, le mois en bref et les pièces reprises récemment.
 */
const accueil = ref<Accueil | null>(null)
const error = ref('')
const poste = computed(() => activePoste())
let lastRequest = 0
async function load() {
	const request = ++lastRequest
	try {
		const response = await getAccueil()
		// Une réponse incomplète (serveur pas encore à jour) ne casse pas la page : on garde l'état d'avant.
		if (!response?.a_faire) throw new Error("L'accueil n'a pas pu être chargé : actualisez la page.")
		if (request === lastRequest) {
			accueil.value = response
			error.value = ''
		}
	} catch (e) {
		if (request === lastRequest && !accueil.value) error.value = (e as Error).message
	}
}

const prenom = computed(() => accueil.value?.prenom || (window.user_fullname || '').split(/\s+/)[0] || '')
const jour = computed(() => {
	const parsed = accueil.value ? new Date(`${accueil.value.jour}T00:00:00`) : new Date()
	const day = Number.isNaN(parsed.getTime()) ? new Date() : parsed
	const text = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(day)
	return text.charAt(0).toUpperCase() + text.slice(1)
})

// Filtre par module de la liste « À faire ».
const modules = computed(() => {
	const all = accueil.value ? [...accueil.value.a_faire.retard, ...accueil.value.a_faire.aujourdhui, ...accueil.value.a_faire.a_valider] : []
	return [...new Set(all.map((item) => item.module))]
})
const filtre = ref('')
const groupes = computed(() => {
	const data = accueil.value?.a_faire
	if (!data) return []
	const keep = (items: AFaire[]) => (filtre.value ? items.filter((item) => item.module === filtre.value) : items)
	return [
		{ key: 'retard', label: 'En retard', ton: 'red', items: keep(data.retard), total: data.totaux.retard },
		{ key: 'aujourdhui', label: "Aujourd'hui", ton: 'amber', items: keep(data.aujourdhui), total: data.totaux.aujourdhui },
		{ key: 'a_valider', label: 'À valider', ton: 'gray', items: keep(data.a_valider), total: data.totaux.a_valider },
	].filter((groupe) => groupe.items.length)
})
const total = computed(() => groupes.value.reduce((sum, groupe) => sum + groupe.items.length, 0))

async function toutLu() {
	if (!accueil.value) return
	await marquerNotificationsLues()
	for (const item of accueil.value.pour_vous) item.lu = true
	accueil.value.non_lus = 0
}

const reload = throttledReload(load, { delayMs: 1500, minIntervalMs: 6000 })
onMounted(() => {
	load()
	connectRealtime<RealtimeEvent>(
		'unicare_bureau_update',
		(event) => {
			if (isForeignChange(event, window.user)) reload()
		},
		load,
	)
})
onBeforeUnmount(closeRealtime)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Accueil' }]" active="accueil">
		<div class="bureau-work tdb accueil">
			<div class="accueil-head">
				<div class="min-w-0 flex-auto">
					<p class="text-sm text-ink-gray-6">{{ jour }} · poste {{ poste.label }}</p>
					<h1 class="text-[26px] font-bold leading-tight text-ink-gray-9">Bonjour{{ prenom ? ` ${prenom}` : '' }}</h1>
					<p v-if="accueil" class="mt-1 text-ink-gray-7" :class="{ 'accueil-resume-retard': accueil.a_faire.totaux.retard > 0 }">{{ resumeJournee(accueil.a_faire.totaux) }}</p>
				</div>
				<CreateMenu />
			</div>

			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!accueil" class="card p-4 text-ink-gray-6">Chargement de votre journée…</p>

			<template v-else>
				<section v-if="accueil.mois.length" class="accueil-mois" aria-label="Le mois en bref">
					<RouterLink v-for="kpi in accueil.mois" :key="`${kpi.module}-${kpi.key}`" :to="{ name: kpi.tableau }" class="card accueil-kpi">
						<span class="text-xs font-medium text-ink-gray-7">{{ kpi.label }}</span>
						<strong class="text-[19px] font-bold tabular-nums text-ink-gray-9">{{ indicateurValue(kpi) }}</strong>
						<small class="truncate text-xs text-ink-gray-6">{{ kpi.module }}<template v-for="(detail, index) in kpi.details.slice(0, 2)" :key="index"> · <span :class="[detail.fort && 'font-semibold', detail.ton && `tdb-ink-${detail.ton}`]">{{ detail.texte }}</span></template></small>
					</RouterLink>
				</section>

				<div class="accueil-grid">
					<section class="card accueil-todo" aria-labelledby="a-faire">
						<div class="accueil-todo-head">
							<h2 id="a-faire" class="text-base font-bold text-ink-gray-9">À faire aujourd'hui</h2>
							<span class="badge tone-gray tabular-nums">{{ total }}</span>
							<span class="flex-auto"></span>
							<div v-if="modules.length > 1" class="accueil-filtres" role="group" aria-label="Filtrer par module">
								<button type="button" class="accueil-filtre" :aria-pressed="!filtre" @click="filtre = ''">Tout</button>
								<button v-for="module in modules" :key="module" type="button" class="accueil-filtre" :aria-pressed="filtre === module" @click="filtre = module">{{ module }}</button>
							</div>
						</div>
						<p v-if="!groupes.length" class="accueil-vide">Rien à faire pour l'instant{{ filtre ? ` dans ${filtre}` : '' }} : tout est à jour.</p>
						<template v-for="groupe in groupes" :key="groupe.key">
							<p class="accueil-groupe" :class="`accueil-groupe-${groupe.ton}`">{{ groupe.label }} · {{ groupe.total }}</p>
							<div v-for="item in groupe.items" :key="`${item.fiche}-${item.name}`" class="accueil-ligne">
								<span class="accueil-icone" :class="MODULE_TONES[item.module] ?? 'tone-gray'" :title="`${item.module} · ${item.nature}`">
									<component :is="ficheIcon(item.fiche)" class="h-[18px] w-[18px]" aria-hidden="true" />
									<span class="sr-only">{{ item.module }}, {{ item.nature }} :</span>
								</span>
								<RouterLink :to="{ name: item.fiche, params: { id: item.name } }" class="accueil-ligne-texte">
									<strong class="block truncate">{{ item.titre }}</strong>
									<small v-if="item.detail" class="block truncate">{{ item.detail }}</small>
								</RouterLink>
								<span v-if="item.badge" class="badge flex-none" :class="`tone-${item.ton}`">{{ item.badge }}</span>
								<RouterLink :to="{ name: item.fiche, params: { id: item.name } }" class="btn-secondary accueil-action">{{ item.action }}</RouterLink>
							</div>
						</template>
					</section>

					<div class="accueil-side">
						<section class="card accueil-panel" aria-labelledby="pour-vous">
							<div class="accueil-panel-head">
								<h2 id="pour-vous" class="text-base font-bold text-ink-gray-9">Pour vous</h2>
								<span v-if="accueil.non_lus" class="badge tone-blue">{{ accueil.non_lus }} nouveau{{ accueil.non_lus > 1 ? 'x' : '' }}</span>
								<span class="flex-auto"></span>
								<button v-if="accueil.non_lus" type="button" class="text-xs font-medium text-link" @click="toutLu">Tout marquer comme lu</button>
							</div>
							<p v-if="!accueil.pour_vous.length" class="accueil-vide">Aucune mention ni alerte.</p>
							<component :is="item.fiche ? 'RouterLink' : 'div'" v-for="item in accueil.pour_vous" :key="item.name" :to="item.fiche ? { name: item.fiche, params: { id: item.document } } : undefined" class="accueil-note" :data-lu="item.lu">
								<span class="accueil-note-icon" :class="item.type === 'mention' ? 'tone-blue' : 'tone-amber'" aria-hidden="true">
									<LucideAtSign v-if="item.type === 'mention'" class="h-3.5 w-3.5" />
									<LucideBell v-else class="h-3.5 w-3.5" />
								</span>
								<span class="min-w-0">
									<span class="block">{{ item.texte }}</span>
									<small class="text-xs text-ink-gray-6">{{ quandText(item.quand) }}<template v-if="item.de"> · {{ item.de }}</template><template v-if="item.module"> · {{ item.module }}</template></small>
								</span>
							</component>
						</section>

						<section class="card accueil-panel" aria-labelledby="recents">
							<div class="accueil-panel-head"><h2 id="recents" class="text-base font-bold text-ink-gray-9">Repris récemment</h2></div>
							<p v-if="!accueil.recents.length" class="accueil-vide">Les pièces que vous modifiez apparaîtront ici.</p>
							<RouterLink v-for="item in accueil.recents" :key="`${item.fiche}-${item.name}`" :to="{ name: item.fiche, params: { id: item.name } }" class="accueil-recent">
								<span class="accueil-icone accueil-icone-small" :class="MODULE_TONES[item.module] ?? 'tone-gray'" :title="item.nature">
									<component :is="ficheIcon(item.fiche)" class="h-4 w-4" aria-hidden="true" />
								</span>
								<span class="min-w-0 flex-auto truncate"><span class="text-ink-gray-6">{{ item.nature }} </span><strong class="tabular-nums">{{ item.name }}</strong><template v-if="item.libelle"> · {{ item.libelle }}</template></span>
								<small class="flex-none text-xs text-ink-gray-6">{{ quandText(item.quand) }}</small>
							</RouterLink>
						</section>
					</div>
				</div>
			</template>
		</div>
	</BureauShell>
</template>
