/** Chargement et écritures d'un article : l'aperçu lit l'essentiel, la fiche (`full`) lit aussi stock, lots, recettes, ordres et mouvements. */
import { getArticle, getArticleFiche } from './api'
import type { ArticleDetail } from './articles'
import { useRecord } from './useRecord'

export function useArticle(id: () => string, changed: () => void = () => {}, full = false) {
	const { record, ...rest } = useRecord<ArticleDetail>(id, full ? getArticleFiche : getArticle, changed)
	return { article: record, ...rest }
}
