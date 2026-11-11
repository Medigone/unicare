<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import FormDialog from '@shared/components/FormDialog.vue'
import { confirmRequest, settleConfirm } from '@/lib/confirm'

/** La fenêtre de confirmation commune, montée une fois : `confirmAction` (lib/confirm.ts) l'ouvre. */
const confirmButton = ref<HTMLButtonElement | null>(null)
watch(confirmRequest, async (request) => {
	if (!request) return
	await nextTick()
	confirmButton.value?.focus()
})
</script>

<template>
	<FormDialog v-if="confirmRequest" :title="confirmRequest.title" :dirty="false" hint="Ctrl + Entrée pour confirmer" @close="settleConfirm(false)" @submit="settleConfirm(true)">
		<p class="whitespace-pre-line">{{ confirmRequest.message }}</p>
		<template #actions>
			<button ref="confirmButton" type="button" :class="confirmRequest.danger ? 'btn-danger' : 'btn-primary'" @click="settleConfirm(true)">{{ confirmRequest.confirmLabel }}</button>
		</template>
	</FormDialog>
</template>
