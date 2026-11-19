<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideImage from '~icons/lucide/image'
import BureauShell from '@/components/BureauShell.vue'
import { apercuSocieteUrl, envoyerLogoSociete, getCommunesSociete, getSociete, saveSociete, supprimerLogoSociete, type Societe, type SocieteValeurs } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'

/** Réglages › Société : l'identité imprimée sur les pièces. Les règles et les vérifications restent côté serveur (bureau_societe.py). */
const societe = ref<Societe | null>(null)
const fiche = ref<SocieteValeurs | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)
const fichier = ref<HTMLInputElement | null>(null)

const MENTIONS: { cle: keyof SocieteValeurs; label: string }[] = [
	{ cle: 'raison_sociale', label: 'Raison sociale' },
	{ cle: 'forme_juridique', label: 'Forme juridique' },
	{ cle: 'capital_social', label: 'Capital social' },
	{ cle: 'adresse', label: 'Adresse du siège' },
	{ cle: 'rc', label: 'RC' },
	{ cle: 'nif', label: 'NIF' },
	{ cle: 'nis', label: 'NIS' },
	{ cle: 'ai', label: 'AI' },
]
const OBLIGATOIRES = new Set(MENTIONS.map((m) => m.cle))

function rempli(valeur: unknown) {
	return typeof valeur === 'number' ? valeur > 0 : String(valeur ?? '').trim() !== ''
}
function prendre(doc: Societe) {
	societe.value = doc
	fiche.value = { ...doc.valeurs, capital_social: doc.valeurs.capital_social ? String(doc.valeurs.capital_social) : '' }
}
async function load() {
	try {
		prendre(await getSociete())
		error.value = ''
	} catch (e) {
		error.value = (e as Error).message
	}
}
onMounted(load)

const initial = computed(() => (societe.value ? JSON.stringify({ ...societe.value.valeurs, capital_social: societe.value.valeurs.capital_social ? String(societe.value.valeurs.capital_social) : '' }) : ''))
const dirty = computed(() => Boolean(fiche.value) && JSON.stringify(fiche.value) !== initial.value)
const lectureSeule = computed(() => !societe.value?.peut_modifier)
const mentions = computed(() => MENTIONS.map((m) => ({ ...m, ok: rempli(fiche.value?.[m.cle]) })))
const faites = computed(() => mentions.value.filter((m) => m.ok).length)
const manque = (cle: keyof SocieteValeurs) => OBLIGATOIRES.has(cle) && !rempli(fiche.value?.[cle])

async function changerWilaya() {
	if (!fiche.value || !societe.value) return
	fiche.value.commune = ''
	societe.value.communes = fiche.value.wilaya ? await getCommunesSociete(fiche.value.wilaya) : []
}

function erreur(e: unknown) {
	actionError.value = (e as Error).message
	if (actionError.value.includes('modifiées par ailleurs')) load()
}
async function enregistrer() {
	if (!societe.value || !fiche.value) return
	busy.value = true
	actionError.value = ''
	notice.value = ''
	try {
		const doc = await saveSociete(societe.value.modified, fiche.value)
		prendre(doc)
		notice.value = doc.avertissements.length ? `Enregistré. ${doc.avertissements.join(' ')}` : 'Enregistré : les prochaines pièces imprimées reprennent ces informations.'
	} catch (e) {
		erreur(e)
	} finally {
		busy.value = false
	}
}
function annuler() {
	if (societe.value) prendre(societe.value)
	actionError.value = ''
}

function choisirLogo() {
	fichier.value?.click()
}
async function envoyerLogo(event: Event) {
	const input = event.target as HTMLInputElement
	const image = input.files?.[0]
	input.value = ''
	if (!image || !societe.value) return
	if (dirty.value) {
		actionError.value = "Enregistrez ou annulez d'abord vos modifications, puis changez le logo."
		return
	}
	busy.value = true
	actionError.value = ''
	try {
		prendre(await envoyerLogoSociete(societe.value.modified, image))
		notice.value = 'Logo enregistré.'
	} catch (e) {
		erreur(e)
	} finally {
		busy.value = false
	}
}
async function retirerLogo() {
	if (!societe.value) return
	if (!(await confirmAction({ title: 'Retirer le logo ?', message: "Les pièces s'imprimeront sans logo.", confirmLabel: 'Retirer le logo', danger: true }))) return
	busy.value = true
	try {
		prendre(await supprimerLogoSociete(societe.value.modified))
	} catch (e) {
		erreur(e)
	} finally {
		busy.value = false
	}
}

onBeforeRouteLeave(async () => {
	if (!dirty.value) return true
	return confirmAction({ title: 'Quitter la page ?', message: 'Les modifications non enregistrées seront perdues.', confirmLabel: 'Quitter sans enregistrer', danger: true })
})

// L'aperçu de l'en-tête et du pied d'une facture, tel que la saisie le donnera.
const lieu = computed(() => {
	const f = fiche.value
	if (!f || !societe.value) return ''
	const commune = societe.value.communes.find((c) => c.name === f.commune)?.nom ?? ''
	const wilaya = societe.value.wilayas.find((w) => w.name === f.wilaya)?.nom ?? ''
	return [f.adresse.trim(), commune, wilaya].filter(Boolean).join(', ')
})
const capitalTexte = computed(() => {
	const valeur = Number(String(fiche.value?.capital_social ?? '').replace(/\s/g, '').replace(',', '.'))
	return valeur > 0 ? new Intl.NumberFormat('fr-FR').format(valeur) : ''
})
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Société' }]" active="societe">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Société</h1>
				<p class="text-sm text-ink-gray-6">Les informations imprimées sur vos factures, devis, bons de livraison et reçus. Obligatoires en Algérie : raison sociale, forme juridique, capital, adresse, RC, NIF, NIS et AI.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!societe || !fiche" class="card p-4 text-ink-gray-6">Chargement…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
			<p v-if="notice" role="status" class="rounded-control tone-green px-3.5 py-2.5">{{ notice }}</p>
			<p v-if="societe && lectureSeule" class="rounded-control tone-gray px-3.5 py-2.5 text-sm">Lecture seule : seuls les comptes qui peuvent modifier la société changent ces informations.</p>

			<div v-if="societe && fiche" class="societe-layout">
				<form class="card societe-form" aria-label="Informations de la société" @submit.prevent="enregistrer">
					<fieldset class="societe-sec" :disabled="lectureSeule || busy">
						<legend class="societe-sec-titre"><span>Identité</span><small>Ce qui figure en tête de chaque pièce.</small></legend>
						<div class="societe-identite">
							<div class="societe-logo">
								<span class="field-label">Logo</span>
								<div class="societe-logo-zone">
									<img v-if="societe.logo" :src="societe.logo" alt="Logo de la société" />
									<template v-else><LucideImage class="h-5 w-5" aria-hidden="true" /><span>Aucun logo</span></template>
								</div>
								<input ref="fichier" type="file" accept="image/png,image/jpeg,image/webp" class="sr-only" aria-label="Choisir le logo" @change="envoyerLogo" />
								<div class="flex flex-wrap gap-1.5">
									<button type="button" class="btn-secondary" @click="choisirLogo">{{ societe.logo ? 'Changer…' : 'Choisir une image…' }}</button>
									<button v-if="societe.logo" type="button" class="btn-ghost text-tone-red" @click="retirerLogo">Retirer</button>
								</div>
								<span class="text-xs text-ink-gray-6">PNG, JPG ou WebP, 2 Mo au plus. Fond blanc, 600 px de large conseillé.</span>
							</div>
							<div class="form-grid flex-1">
								<div class="form-field col-span-2">
									<label class="field-label" for="s-rs">Raison sociale</label>
									<input id="s-rs" v-model="fiche.raison_sociale" class="field-input" :aria-invalid="manque('raison_sociale')" />
									<p class="field-note">Dans l'ERP, la société s'appelle « {{ societe.nom_erp }} » ; c'est ce nom-ci qui s'imprime.</p>
								</div>
								<div class="form-field" :class="manque('forme_juridique') && 'is-manque'">
									<label class="field-label" for="s-fj">Forme juridique</label>
									<input id="s-fj" v-model="fiche.forme_juridique" class="field-input" placeholder="SARL, EURL, SPA…" />
									<p v-if="manque('forme_juridique')" class="field-note">Obligatoire sur la facture</p>
								</div>
								<div class="form-field" :class="manque('capital_social') && 'is-manque'">
									<label class="field-label" for="s-cap">Capital social (DA)</label>
									<input id="s-cap" v-model="fiche.capital_social" class="field-input tabular-nums" inputmode="decimal" placeholder="ex. 1 000 000" />
									<p v-if="manque('capital_social')" class="field-note">Obligatoire sur la facture</p>
								</div>
							</div>
						</div>
					</fieldset>

					<fieldset class="societe-sec" :disabled="lectureSeule || busy">
						<legend class="societe-sec-titre"><span>Coordonnées</span></legend>
						<div class="form-grid">
							<div class="form-field col-span-2" :class="manque('adresse') && 'is-manque'">
								<label class="field-label" for="s-adr">Adresse du siège</label>
								<input id="s-adr" v-model="fiche.adresse" class="field-input" placeholder="Rue, numéro, zone" />
								<p v-if="manque('adresse')" class="field-note">Obligatoire sur la facture</p>
							</div>
							<div class="form-field">
								<label class="field-label" for="s-wil">Wilaya</label>
								<select id="s-wil" v-model="fiche.wilaya" class="field-input" @change="changerWilaya">
									<option value="">Choisir…</option>
									<option v-for="w in societe.wilayas" :key="w.name" :value="w.name">{{ w.code ? `${w.code} · ` : '' }}{{ w.nom || w.name }}</option>
								</select>
							</div>
							<div class="form-field">
								<label class="field-label" for="s-com">Commune</label>
								<select id="s-com" v-model="fiche.commune" class="field-input" :disabled="!fiche.wilaya">
									<option value="">{{ fiche.wilaya ? 'Choisir…' : "Choisir d'abord la wilaya" }}</option>
									<option v-for="c in societe.communes" :key="c.name" :value="c.name">{{ c.nom || c.name }}</option>
								</select>
							</div>
							<div class="form-field">
								<label class="field-label" for="s-tel">Téléphone</label>
								<input id="s-tel" v-model="fiche.telephone" class="field-input" type="tel" placeholder="ex. 023 00 00 00" />
							</div>
							<div class="form-field">
								<label class="field-label" for="s-mail">E-mail</label>
								<input id="s-mail" v-model="fiche.email" class="field-input" type="email" placeholder="contact@…" />
							</div>
							<div class="form-field col-span-2">
								<label class="field-label" for="s-web">Site web</label>
								<input id="s-web" v-model="fiche.site_web" class="field-input" placeholder="ex. unicarepharma.dz" />
							</div>
						</div>
					</fieldset>

					<fieldset class="societe-sec" :disabled="lectureSeule || busy">
						<legend class="societe-sec-titre"><span>Identifiants fiscaux</span><small>Imprimés en pied de chaque page. Chiffres seulement pour le NIF, le NIS et l'AI.</small></legend>
						<div class="form-grid">
							<div class="form-field" :class="manque('rc') && 'is-manque'">
								<label class="field-label" for="s-rc">N° RC (registre de commerce)</label>
								<input id="s-rc" v-model="fiche.rc" class="field-input" placeholder="ex. 16/00-1234567B21" />
								<p v-if="manque('rc')" class="field-note">Obligatoire</p>
							</div>
							<div class="form-field" :class="manque('nif') && 'is-manque'">
								<label class="field-label" for="s-nif">NIF</label>
								<input id="s-nif" v-model="fiche.nif" class="field-input tabular-nums" inputmode="numeric" placeholder="15 chiffres" />
								<p class="field-note">{{ manque('nif') ? 'Obligatoire · ' : '' }}15 chiffres</p>
							</div>
							<div class="form-field" :class="manque('nis') && 'is-manque'">
								<label class="field-label" for="s-nis">NIS</label>
								<input id="s-nis" v-model="fiche.nis" class="field-input tabular-nums" inputmode="numeric" placeholder="15 chiffres" />
								<p class="field-note">{{ manque('nis') ? 'Obligatoire · ' : '' }}15 chiffres</p>
							</div>
							<div class="form-field" :class="manque('ai') && 'is-manque'">
								<label class="field-label" for="s-ai">N° AI (article d'imposition)</label>
								<input id="s-ai" v-model="fiche.ai" class="field-input tabular-nums" inputmode="numeric" placeholder="11 chiffres" />
								<p class="field-note">{{ manque('ai') ? 'Obligatoire · ' : '' }}11 chiffres</p>
							</div>
						</div>
					</fieldset>

					<fieldset class="societe-sec" :disabled="lectureSeule || busy">
						<legend class="societe-sec-titre"><span>Banque</span><small>Imprimés dans la partie « Règlement » des factures.</small></legend>
						<div class="form-grid">
							<div class="form-field">
								<label class="field-label" for="s-bq">Banque et agence</label>
								<input id="s-bq" v-model="fiche.banque" class="field-input" placeholder="ex. BNA, agence de Rouiba" />
							</div>
							<div class="form-field">
								<label class="field-label" for="s-rib">RIB</label>
								<input id="s-rib" v-model="fiche.rib" class="field-input tabular-nums" inputmode="numeric" placeholder="20 chiffres" />
								<p class="field-note">20 chiffres</p>
							</div>
						</div>
					</fieldset>

					<div v-if="!lectureSeule" class="stock-barre" :class="dirty && 'is-dirty'">
						<span class="flex-auto text-sm" :class="dirty ? 'font-medium text-tone-amber' : 'text-ink-gray-6'">{{ dirty ? 'Modifications non enregistrées' : 'Aucune modification' }}</span>
						<button type="button" class="btn-ghost" :disabled="busy || !dirty" @click="annuler">Annuler</button>
						<button type="submit" class="btn-primary" :disabled="busy || !dirty || !fiche.raison_sociale.trim()">Enregistrer</button>
					</div>
				</form>

				<aside class="societe-cote" aria-label="État et aperçu">
					<section class="card societe-carte" aria-labelledby="s-etat">
						<div class="flex items-center justify-between gap-2">
							<h2 id="s-etat" class="text-[15px] font-semibold">Mentions obligatoires</h2>
							<span class="badge" :class="faites === mentions.length ? 'tone-green' : 'tone-orange'">{{ faites }} sur {{ mentions.length }}</span>
						</div>
						<div class="compta-segments" aria-hidden="true">
							<span v-for="m in mentions" :key="m.cle" :class="m.ok ? '' : 'is-attention'"></span>
						</div>
						<ul class="societe-mentions">
							<li v-for="m in mentions" :key="m.cle"><span class="compta-pastille" :class="m.ok ? '' : 'is-attention'" aria-hidden="true"></span>{{ m.label }}<span class="sr-only">{{ m.ok ? ' : renseigné' : ' : manquant' }}</span></li>
						</ul>
						<p class="text-xs text-ink-gray-6">Tant qu'une mention manque, elle s'imprime « — » sur les pièces.</p>
					</section>

					<section class="card societe-carte" aria-labelledby="s-apercu">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<h2 id="s-apercu" class="text-[15px] font-semibold">Sur vos pièces</h2>
							<a :href="apercuSocieteUrl()" target="_blank" rel="noopener noreferrer" class="btn-ghost">Facture d'exemple (PDF)<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" /></a>
						</div>
						<div class="societe-doc" aria-label="Aperçu de l'en-tête et du pied d'une facture">
							<div class="flex justify-between gap-3">
								<div class="flex min-w-0 flex-col gap-px">
									<img v-if="societe.logo" :src="societe.logo" alt="" class="societe-doc-logo" />
									<b class="text-[13px]">{{ fiche.raison_sociale || '—' }}</b>
									<span><span :class="!fiche.forme_juridique && 'societe-trou'">{{ fiche.forme_juridique || '[forme]' }}</span> au capital de <span :class="!capitalTexte && 'societe-trou'">{{ capitalTexte || '[capital]' }}</span> DA</span>
									<span :class="!lieu && 'societe-trou'">{{ lieu || '[adresse]' }}</span>
								</div>
								<div class="flex-none text-right"><b class="text-[13px] tracking-wider">FACTURE</b><br /><span class="text-ink-gray-6">N° …</span></div>
							</div>
							<div class="societe-doc-corps">Tiers, lignes et totaux</div>
							<div class="societe-doc-pied">
								<span>
									{{ fiche.raison_sociale }}
									<template v-for="cle in (['rc', 'nif', 'nis', 'ai'] as const)" :key="cle"> · {{ cle.toUpperCase() }} <span :class="!fiche[cle] && 'societe-trou'">{{ fiche[cle] || '—' }}</span></template>
								</span>
								<b class="whitespace-nowrap">Page 1/1</b>
							</div>
						</div>
						<p class="text-xs text-ink-gray-6">L'aperçu suit la saisie ; la facture d'exemple reprend les informations enregistrées.</p>
					</section>
				</aside>
			</div>
		</div>
	</BureauShell>
</template>
