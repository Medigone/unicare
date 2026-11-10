import frappeUIPreset from 'frappe-ui/tailwind'
import unicarePreset from '../shared/tailwind.preset.js'

export default {
	presets: [frappeUIPreset, unicarePreset],
	content: ['./index.html', './src/**/*.{vue,js,ts}', '../shared/**/*.{vue,ts}'],
	plugins: [],
}
