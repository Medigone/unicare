<script setup lang="ts">
import { computed, ref } from 'vue'
import { compactAmount, niceScale, SERIES_COLORS, valueText, type Tendance } from '@/lib/tableaux'

/**
 * Barres groupées, une couleur par série (ordre fixe), axe unique partant de zéro.
 * Survol ou focus d'une période : bulle avec les valeurs exactes. Un tableau masqué reprend les chiffres pour les lecteurs d'écran.
 */
const props = defineProps<{ tendance: Tendance }>()
const amount = (value: number | null | undefined) => valueText(value, props.tendance.unite)

const WIDTH = 600
const HEIGHT = 232
const LEFT = 44
const TOP = 12
const BOTTOM = 200
const plotWidth = WIDTH - LEFT - 4

const scale = computed(() => niceScale(Math.max(0, ...props.tendance.points.flatMap((point) => point.valeurs))))
const band = computed(() => plotWidth / Math.max(props.tendance.points.length, 1))
const seriesCount = computed(() => Math.max(props.tendance.series.length, 1))
// Barres fines : au plus 24 px, 2 px d'écart entre séries d'un même groupe.
const barWidth = computed(() => Math.min(24, (band.value * 0.66 - 2 * (seriesCount.value - 1)) / seriesCount.value))
const groupWidth = computed(() => barWidth.value * seriesCount.value + 2 * (seriesCount.value - 1))
const y = (value: number) => BOTTOM - (Math.max(value, 0) / scale.value.top) * (BOTTOM - TOP)

const bars = computed(() =>
	props.tendance.points.map((point, index) => {
		const start = LEFT + band.value * index + (band.value - groupWidth.value) / 2
		return {
			index,
			center: LEFT + band.value * index + band.value / 2,
			rects: point.valeurs.map((value, serie) => {
				const top = y(value)
				// Bas carré sur la ligne de base : le rectangle déborde sous l'axe, coupé par le clip.
				return { x: start + serie * (barWidth.value + 2), y: top, height: value > 0 ? BOTTOM - top + 4 : 0, color: SERIES_COLORS[serie] }
			}),
		}
	}),
)

const hover = ref<number | null>(null)
const tip = computed(() => {
	if (hover.value == null) return null
	const point = props.tendance.points[hover.value]
	const center = bars.value[hover.value].center
	return { point, left: `${(center / WIDTH) * 100}%`, alignRight: center > WIDTH * 0.7 }
})
const clipId = `plot-${Math.random().toString(36).slice(2, 8)}`
const lastIndex = computed(() => props.tendance.points.length - 1)
const empty = computed(() => props.tendance.points.every((point) => point.valeurs.every((value) => !value)))
</script>

<template>
	<div class="bar-chart">
		<div v-if="tendance.series.length > 1" class="chart-legend">
			<span v-for="(serie, index) in tendance.series" :key="serie.key" class="chart-legend-item">
				<span class="chart-swatch" :style="{ background: SERIES_COLORS[index] }" aria-hidden="true"></span>{{ serie.label }}
			</span>
		</div>
		<div class="relative" @pointerleave="hover = null">
			<svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="block h-auto w-full" role="img" :aria-label="tendance.titre">
				<defs>
					<clipPath :id="clipId"><rect :x="LEFT" :y="0" :width="plotWidth" :height="BOTTOM" /></clipPath>
				</defs>
				<g v-for="tick in scale.ticks" :key="tick">
					<line v-if="tick > 0" :x1="LEFT" :x2="WIDTH - 4" :y1="y(tick)" :y2="y(tick)" class="chart-grid" />
					<text :x="LEFT - 6" :y="y(tick) + 4" text-anchor="end" class="chart-axis">{{ compactAmount(tick) }}</text>
				</g>
				<line :x1="LEFT" :x2="WIDTH - 4" :y1="BOTTOM" :y2="BOTTOM" class="chart-base" />
				<g :clip-path="`url(#${clipId})`">
					<template v-for="group in bars" :key="group.index">
						<rect v-for="(rect, serie) in group.rects" :key="serie" :x="rect.x" :y="rect.y" :width="barWidth" :height="rect.height" rx="4" :fill="rect.color" :opacity="hover == null || hover === group.index ? 1 : 0.45" />
					</template>
				</g>
				<text
					v-for="group in bars"
					:key="`l${group.index}`"
					:x="group.center"
					:y="BOTTOM + 18"
					text-anchor="middle"
					class="chart-axis"
					:class="group.index === lastIndex && 'chart-axis-current'"
				>
					{{ tendance.points[group.index].label }}
				</text>
				<!-- Zones de survol : toute la hauteur de la période, plus large que les barres. -->
				<rect
					v-for="group in bars"
					:key="`h${group.index}`"
					:x="LEFT + band * group.index"
					:y="0"
					:width="band"
					:height="HEIGHT"
					fill="transparent"
					tabindex="0"
					class="chart-hit"
					:aria-label="`${tendance.points[group.index].titre} : ${tendance.series.map((serie, index) => `${serie.label} ${amount(tendance.points[group.index].valeurs[index])}`).join(', ')}`"
					@pointerenter="hover = group.index"
					@focus="hover = group.index"
					@blur="hover = null"
				/>
			</svg>
			<p v-if="empty" class="chart-empty">Rien sur ces périodes pour l'instant.</p>
			<div v-if="tip" class="chart-tip" :class="tip.alignRight && 'chart-tip-right'" :style="{ left: tip.left }" role="status">
				<p class="font-semibold text-ink-gray-9">{{ tip.point.titre }}</p>
				<p v-for="(serie, index) in tendance.series" :key="serie.key" class="flex items-center gap-2">
					<span class="chart-swatch" :style="{ background: SERIES_COLORS[index] }" aria-hidden="true"></span>
					<span class="text-ink-gray-7">{{ serie.label }}</span>
					<span class="ml-auto pl-3 font-medium tabular-nums text-ink-gray-9">{{ amount(tip.point.valeurs[index]) }}</span>
				</p>
			</div>
		</div>
		<table class="sr-only">
			<caption>{{ tendance.titre }}</caption>
			<thead>
				<tr>
					<th scope="col">Période</th>
					<th v-for="serie in tendance.series" :key="serie.key" scope="col">{{ serie.label }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="point in tendance.points" :key="point.titre">
					<th scope="row">{{ point.titre }}</th>
					<td v-for="(value, index) in point.valeurs" :key="index">{{ amount(value) }}</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>
