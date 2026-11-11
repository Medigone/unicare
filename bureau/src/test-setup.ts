/** Préparation des tests : la directive globale `v-search`, comme dans l'application (main.ts). */
import { config } from '@vue/test-utils'
import { vSearch } from './lib/searchSelect'

config.global.directives = { ...config.global.directives, search: vSearch }
