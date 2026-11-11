<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AchatDialog from './AchatDialog.vue'
import ArticleDialog from './ArticleDialog.vue'
import ClientDialog from './ClientDialog.vue'
import FournisseurDialog from './FournisseurDialog.vue'
import InventaireDialog from './InventaireDialog.vue'
import MouvementDialog from './MouvementDialog.vue'
import OrdreDialog from './OrdreDialog.vue'
import PaiementAssistant from './PaiementAssistant.vue'
import RecetteDialog from './RecetteDialog.vue'
import VenteDialog from './VenteDialog.vue'
import { CREER_ITEMS, creating, itemForLetter } from '@/lib/creer'

/**
 * Fenêtres de création ouvertes par le bouton « Créer » ou par les raccourcis : N puis une lettre, de n'importe quelle
 * page (pas pendant une saisie). Une fois créé, on arrive sur la fiche.
 */
const router = useRouter()
const item = computed(() => CREER_ITEMS.find((entry) => entry.key === creating.value))

function close() {
	creating.value = null
}
function onCreated(name: string) {
	const fiche = item.value?.fiche
	creating.value = null
	if (fiche) router.push({ name: fiche, params: { id: name } })
}

let waiting = false
let timer: ReturnType<typeof setTimeout> | null = null
function typing(target: EventTarget | null) {
	const element = target as HTMLElement | null
	return Boolean(element && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName)))
}
function onKey(event: KeyboardEvent) {
	if (event.ctrlKey || event.metaKey || event.altKey || typing(event.target) || creating.value || document.querySelector('.dialog-scrim')) return
	const key = event.key.toLowerCase()
	if (waiting) {
		waiting = false
		if (timer) clearTimeout(timer)
		const found = itemForLetter(key)
		if (found) {
			event.preventDefault()
			creating.value = found.key
		}
		return
	}
	if (key === 'n') {
		waiting = true
		timer = setTimeout(() => (waiting = false), 1500)
	}
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
	<VenteDialog v-if="creating === 'devis'" kind="devis" @close="close" @created="onCreated" />
	<VenteDialog v-else-if="creating === 'commande'" kind="commande" @close="close" @created="onCreated" />
	<PaiementAssistant v-else-if="creating === 'paiement'" @close="close" @created="onCreated" />
	<OrdreDialog v-else-if="creating === 'ordre'" @close="close" @created="onCreated" />
	<ClientDialog v-else-if="creating === 'client'" @close="close" @created="onCreated" />
	<AchatDialog v-else-if="creating === 'commande_achat'" kind="commande" @close="close" @created="onCreated" />
	<AchatDialog v-else-if="creating === 'devis_fournisseur'" kind="devis" @close="close" @created="onCreated" />
	<FournisseurDialog v-else-if="creating === 'fournisseur'" @close="close" @created="onCreated" />
	<MouvementDialog v-else-if="creating === 'mouvement'" @close="close" @created="onCreated" />
	<InventaireDialog v-else-if="creating === 'inventaire'" @close="close" @created="onCreated" />
	<ArticleDialog v-else-if="creating === 'article'" @close="close" @created="onCreated" />
	<RecetteDialog v-else-if="creating === 'recette'" @close="close" @created="onCreated" />
</template>
