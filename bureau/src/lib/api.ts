/** Appels du poste de bureau. Les règles restent côté serveur (unicare/api/bureau_*.py). */
import type { ActivityApi, ActivityFeedData, Mention } from '@shared/activity'
import { call } from '@shared/api'
import type { BulkItem, BulkOptions, BulkResult, Option } from '@/types'
import type { ArticleChoice, ArticleDetail, ArticleOptions, ArticlesResponse, ArticleValues, ArticleView } from './articles'
import type { CommandeDetail, CommandeOptions, CommandesResponse, CommandeView, StatusAction } from './commandes'
import type { PaiementDetail, PaiementOptions, PaiementsResponse, PaiementType, PaiementView, PieceOuverte } from './paiements'
import type { FactureDetail, FactureOptions, FacturesResponse, FactureView } from './factures'
import type { LivraisonDetail, LivraisonsResponse, LivraisonView } from './livraisons'
import type { DevisAction, DevisArticleChoice, DevisDetail, DevisOptions, DevisResponse, DevisView } from './devis'
import type { AchatArticleChoice, AchatLineValues } from './achats'
import type { FactureAchatDetail, FactureAchatOptions, FacturesAchatResponse, FactureAchatValues, FactureAchatView } from './facturesAchat'
import type { LotDetail, LotOptions, LotsResponse, LotValues, LotView } from './lots'
import type { EtatStockOptions, EtatStockResponse, EtatStockView, LigneStockDetail } from './etatStock'
import type { DepotDetail, DepotOptions, DepotsResponse, DepotValues, DepotView } from './depots'
import type { ReceptionDetail, ReceptionPrepChange, ReceptionsResponse, ReceptionView } from './receptions'
import type { CommandeAchatDetail, CommandeAchatOptions, CommandesAchatResponse, CommandeAchatView } from './commandesAchat'
import type { DevisFournisseurDetail, DevisFournisseurOptions, DevisFournisseurResponse, DevisFournisseurView } from './devisFournisseur'
import type { FournisseurChoice, FournisseurDetail, FournisseurOptions, FournisseursResponse, FournisseurValues, FournisseurView } from './fournisseurs'
import type { ClientChoice, ClientDetail, ClientOptions, ClientsResponse, ClientValues, ClientView, CommuneChoice } from './clients'
import type { Condition, FilterField } from './filters'
import { conditionsForServer } from './filters'
import type { ListLayout } from './listViews'
import type { ListPaging } from './useServerList'
import type { VersionModule } from './versions'

const LISTS = 'unicare.api.bureau_list'

export const HOME_PATH = '/bureau'
export const LOGIN_PATH = '/bureau/connexion'

/** Retour après connexion : une page du poste seulement (même règle que `safe_redirect` côté serveur). */
export function safeRedirect(target: string | null | undefined) {
	const value = (target || '').trim()
	if (!/^\/bureau(?:[/?#]|$)/.test(value) || value.startsWith(LOGIN_PATH)) return HOME_PATH
	return value
}

/** Session expirée : connexion, avec la page en cours pour y revenir ensuite. */
export function redirectToLogin() {
	const { pathname, search, hash } = window.location
	const target = safeRedirect(pathname + search + hash)
	window.location.assign(target === HOME_PATH ? LOGIN_PATH : `${LOGIN_PATH}?redirect-to=${encodeURIComponent(target)}`)
}

/** Connexion Frappe (même méthode que la page /login du site). */
export const login = (usr: string, pwd: string) => call<string>('login', { usr, pwd }, true)

/** Envoi du lien de réinitialisation : réponse identique que le compte existe ou non. */
export const resetPassword = (user: string) => call('frappe.core.doctype.user.user.reset_password', { user }, true)

/** Déconnexion (la session du Desk est la même), puis retour à la connexion du poste. */
export async function logout() {
	await call('logout', {}, true)
	window.location.href = LOGIN_PATH
}

/** La cloche d'une ligne : même écriture que le cœur du Desk, sans toucher à `modified`. */
export const setBell = (doctype: string, name: string, on: boolean) => call('frappe.desk.like.toggle_like', { doctype, name, add: on ? 'Yes' : 'No' }, true)

/** Un filtre de `List Filter`, partagé avec le Desk. `dropped` compte les conditions dont le champ n'est plus disponible. */
export interface SavedFilter {
	name: string
	label: string
	is_global: boolean
	can_delete: boolean
	conditions: Omit<Condition, 'id'>[]
	dropped: number
}

export const getSavedFilters = (doctype: string) => call<{ filters: SavedFilter[]; can_share: boolean }>(`${LISTS}.get_saved_filters`, { doctype })
export const saveFilter = (doctype: string, label: string, conditions: Condition[], isGlobal: boolean) =>
	call<string>(`${LISTS}.save_filter`, { doctype, label, conditions: conditionsForServer(conditions), is_global: isGlobal ? 1 : 0 }, true)
export const deleteSavedFilter = (name: string) => call(`${LISTS}.delete_saved_filter`, { name }, true)
export const searchFilterLink = (listDoctype: string, doctype: string, field: string, search: string) =>
	call<Option[]>(`${LISTS}.search_filter_link`, { list_doctype: listDoctype, doctype, field, search: search.trim() || undefined })

/** Une vue enregistrée d'une liste. `dropped` compte les colonnes et les filtres dont le champ n'est plus disponible. */
export interface SavedListView {
	name: string
	label: string
	is_global: boolean
	can_edit: boolean
	config: ListLayout
	dropped: number
}

export const getListViews = (doctype: string) => call<{ views: SavedListView[]; default: string | null; can_share: boolean }>(`${LISTS}.get_list_views`, { doctype })
export const saveListView = (doctype: string, label: string, layout: ListLayout, isGlobal: boolean, name?: string) =>
	call<string>(
		`${LISTS}.save_list_view`,
		{ doctype, label, config: { columns: layout.columns, sort: layout.sort, view: layout.view, conditions: conditionsForServer(layout.conditions.map((condition, id) => ({ ...condition, id }))) }, is_global: isGlobal ? 1 : 0, name },
		true,
	)
export const deleteListView = (name: string) => call(`${LISTS}.delete_list_view`, { name }, true)
export const setDefaultListView = (doctype: string, name: string | null) => call(`${LISTS}.set_default_list_view`, { doctype, name: name ?? undefined }, true)

/** Champs du doctype qui ne figurent pas dans la liste, pour les lignes exportées : { ligne: { « doctype.champ »: valeur } }. */
export const getExportValues = (doctype: string, names: string[], fields: { doctype: string; field: string }[]) =>
	call<Record<string, Record<string, string | number>>>(`${LISTS}.get_export_values`, { doctype, names, fields }, true)
/** Classeur Excel des lignes données, en base 64. */
export const exportXlsx = (title: string, headers: string[], rows: (string | number)[][]) => call<string>(`${LISTS}.export_xlsx`, { title, headers, rows }, true)

/** Un lot d'action groupée enregistre plusieurs documents : il a droit à plus de temps qu'une requête ordinaire. */
const BULK_TIMEOUT_MS = 120 * 1000
const bulkItems = (rows: BulkItem[]) => rows.map(({ name, modified }) => ({ name, modified }))

/** Actions communes à toutes les listes : les droits et les champs permis sont décidés par le serveur. */
const BULK = 'unicare.api.bureau_bulk'
export const getBulkOptions = (doctype: string) => call<BulkOptions>(`${BULK}.get_bulk_options`, { doctype })
export const bulkUpdate = (doctype: string, rows: BulkItem[], fieldname: string, value: string) =>
	call<BulkResult>(`${BULK}.bulk_update`, { doctype, items: bulkItems(rows), fieldname, value }, true, BULK_TIMEOUT_MS)
export const bulkDelete = (doctype: string, rows: BulkItem[]) => call<BulkResult>(`${BULK}.bulk_delete`, { doctype, items: bulkItems(rows) }, true, BULK_TIMEOUT_MS)
export const bulkAddTags = (doctype: string, rows: BulkItem[], tags: string[]) =>
	call<BulkResult>(`${BULK}.bulk_add_tags`, { doctype, items: bulkItems(rows), tags }, true, BULK_TIMEOUT_MS)
export const addDocTag = (doctype: string, row: BulkItem, tag: string) =>
	call<{ tags: string[] }>(`${BULK}.add_doc_tag`, { doctype, name: row.name, modified: row.modified, tag }, true)
export const removeDocTag = (doctype: string, row: BulkItem, tag: string) =>
	call<{ tags: string[] }>(`${BULK}.remove_doc_tag`, { doctype, name: row.name, modified: row.modified, tag }, true)
export const getBulkTags = (search: string) => call<string[]>(`${BULK}.get_bulk_tags`, { search: search.trim() || undefined })
export const searchBulkLink = (doctype: string, fieldname: string, search: string) =>
	call<Option[]>(`${BULK}.search_bulk_link`, { doctype, fieldname, search: search.trim() || undefined })

/** Clients : liste, aperçu, fiche, création et modification. */
const CLIENTS = 'unicare.api.bureau_clients'

export const getClients = (view: ClientView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<ClientsResponse>(`${CLIENTS}.get_clients`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getClient = (name: string) => call<ClientDetail>(`${CLIENTS}.get_client`, { name })
/** La fiche : l'aperçu, plus les ventes, la comptabilité et le résumé des commentaires. */
export const getClientFiche = (name: string) => call<ClientDetail>(`${CLIENTS}.get_client`, { name, full: 1 })
export const getClientOptions = () => call<ClientOptions>(`${CLIENTS}.get_client_options`)
export const searchCommunes = (search: string) => call<CommuneChoice[]>(`${CLIENTS}.search_communes`, { search: search.trim() || undefined })
export const searchClients = (search: string) => call<ClientChoice[]>(`${CLIENTS}.search_clients`, { search: search.trim() || undefined })
export const createClient = (values: ClientValues) => call<{ name: string }>(`${CLIENTS}.create_client`, { values }, true)
export const updateClient = (client: ClientDetail, values: ClientValues) => call<ClientDetail>(`${CLIENTS}.update_client`, { name: client.name, modified: client.modified, values }, true)
export const setClientPiece = (client: ClientDetail, piece: string, fileUrl: string) =>
	call<ClientDetail>(`${CLIENTS}.set_client_piece`, { name: client.name, modified: client.modified, piece, file_url: fileUrl }, true)

/** Commentaires et activité d'un client, pour le fil commun (mêmes commentaires que la timeline du Desk). */
export function clientActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${CLIENTS}.get_client_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${CLIENTS}.add_client_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${CLIENTS}.update_client_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${CLIENTS}.delete_client_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Fournisseurs : liste, aperçu, fiche, création et modification. */
const FOURNISSEURS = 'unicare.api.bureau_fournisseurs'

export const getFournisseurs = (view: FournisseurView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<FournisseursResponse>(`${FOURNISSEURS}.get_fournisseurs`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getFournisseur = (name: string) => call<FournisseurDetail>(`${FOURNISSEURS}.get_fournisseur`, { name })
export const getFournisseurFiche = (name: string) => call<FournisseurDetail>(`${FOURNISSEURS}.get_fournisseur`, { name, full: 1 })
export const getFournisseurOptions = () => call<FournisseurOptions>(`${FOURNISSEURS}.get_fournisseur_options`)
/** `actifs` : seulement les fournisseurs à qui l'on peut acheter, pour choisir celui d'une pièce. */
export const searchFournisseurs = (search: string, actifs = false) => call<FournisseurChoice[]>(`${FOURNISSEURS}.search_fournisseurs`, { search: search.trim() || undefined, actifs: actifs ? 1 : undefined })
export const createFournisseur = (values: FournisseurValues) => call<{ name: string }>(`${FOURNISSEURS}.create_fournisseur`, { values }, true)
export const updateFournisseur = (fournisseur: FournisseurDetail, values: FournisseurValues) =>
	call<FournisseurDetail>(`${FOURNISSEURS}.update_fournisseur`, { name: fournisseur.name, modified: fournisseur.modified, values }, true)
export const setFournisseurPiece = (fournisseur: FournisseurDetail, piece: string, fileUrl: string) =>
	call<FournisseurDetail>(`${FOURNISSEURS}.set_fournisseur_piece`, { name: fournisseur.name, modified: fournisseur.modified, piece, file_url: fileUrl }, true)

export function fournisseurActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${FOURNISSEURS}.get_fournisseur_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${FOURNISSEURS}.add_fournisseur_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${FOURNISSEURS}.update_fournisseur_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${FOURNISSEURS}.delete_fournisseur_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Articles : liste, aperçu, fiche, création et modification. */
const ARTICLES = 'unicare.api.bureau_articles'

export const getArticles = (view: ArticleView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<ArticlesResponse>(`${ARTICLES}.get_articles`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getArticle = (name: string) => call<ArticleDetail>(`${ARTICLES}.get_article`, { name })
/** La fiche : l'aperçu, plus le stock par dépôt, les lots, les recettes, les ordres, les achats et ventes. */
export const getArticleFiche = (name: string) => call<ArticleDetail>(`${ARTICLES}.get_article`, { name, full: 1 })
export const getArticleOptions = () => call<ArticleOptions>(`${ARTICLES}.get_article_options`)
export const searchArticles = (search: string) => call<ArticleChoice[]>(`${ARTICLES}.search_articles`, { search: search.trim() || undefined })
export const createArticle = (values: ArticleValues) => call<{ name: string }>(`${ARTICLES}.create_article`, { values }, true)
export const updateArticle = (article: ArticleDetail, values: ArticleValues) => call<ArticleDetail>(`${ARTICLES}.update_article`, { name: article.name, modified: article.modified, values }, true)

/** Commentaires et activité d'un article, pour le fil commun. */
export function articleActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${ARTICLES}.get_article_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${ARTICLES}.add_article_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${ARTICLES}.update_article_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${ARTICLES}.delete_article_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Devis : liste, aperçu, fiche, création et cycle (valider, commande, perdu, annuler). */
const DEVIS = 'unicare.api.bureau_devis'

export const getDevisList = (view: DevisView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<DevisResponse>(`${DEVIS}.get_devis_list`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getDevis = (name: string) => call<DevisDetail>(`${DEVIS}.get_devis`, { name })
export const getDevisOptions = () => call<DevisOptions>(`${DEVIS}.get_devis_options`)
export const searchDevisArticles = (search: string) => call<DevisArticleChoice[]>(`${DEVIS}.search_devis_articles`, { search: search.trim() || undefined })

export interface DevisValues {
	client?: string
	valable?: string
	taxes?: string
	lignes?: { article: string; quantite: number; prix: number | null }[]
}
export const createDevis = (values: DevisValues) => call<{ name: string }>(`${DEVIS}.create_devis`, { values }, true)
export const updateDevis = (devis: DevisDetail, values: DevisValues) => call<DevisDetail>(`${DEVIS}.update_devis`, { name: devis.name, modified: devis.modified, values }, true)

/** Actions du cycle qui ne prennent que le devis affiché. */
const DEVIS_METHODS: Partial<Record<DevisAction, string>> = { valider: 'validate_devis', annuler: 'cancel_devis' }
export const runDevisAction = (devis: DevisDetail, action: 'valider' | 'annuler') => call<DevisDetail>(`${DEVIS}.${DEVIS_METHODS[action]}`, { name: devis.name, modified: devis.modified }, true)
export const deleteDevis = (devis: DevisDetail) => call<{ deleted: string }>(`${DEVIS}.delete_devis`, { name: devis.name, modified: devis.modified }, true)
export const markDevisLost = (devis: DevisDetail, raison: string, precisions: string) => call<DevisDetail>(`${DEVIS}.mark_lost`, { name: devis.name, modified: devis.modified, raison, precisions }, true)
export const createDevisCommande = (devis: DevisDetail, livraison: string) => call<{ commande: string; devis: DevisDetail }>(`${DEVIS}.create_commande`, { name: devis.name, modified: devis.modified, livraison }, true)

/** Impression du Desk : aperçu et PDF, avec le format par défaut du devis. */
export const devisPrintUrl = (name: string) => `/printview?doctype=Quotation&name=${encodeURIComponent(name)}&trigger_print=1`
export const devisPdfUrl = (name: string) => `/api/method/frappe.utils.print_format.download_pdf?doctype=Quotation&name=${encodeURIComponent(name)}`

/** Commentaires et activité d'un devis, pour le fil commun. */
export function devisActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${DEVIS}.get_devis_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${DEVIS}.add_devis_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${DEVIS}.update_devis_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${DEVIS}.delete_devis_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Commandes client : liste, aperçu, fiche, création et cycle (valider, livraison, facture, statuts, annuler). */
const COMMANDES = 'unicare.api.bureau_commandes'

export const getCommandes = (view: CommandeView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<CommandesResponse>(`${COMMANDES}.get_commandes`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getCommande = (name: string) => call<CommandeDetail>(`${COMMANDES}.get_commande`, { name })
export const getCommandeOptions = () => call<CommandeOptions>(`${COMMANDES}.get_commande_options`)

export interface CommandeValues {
	client?: string
	livraison?: string
	taxes?: string
	reference?: string
	lignes?: { article: string; quantite: number; prix: number | null }[]
}
export const createCommande = (values: CommandeValues) => call<{ name: string }>(`${COMMANDES}.create_commande`, { values }, true)
export const updateCommande = (commande: CommandeDetail, values: CommandeValues) => call<CommandeDetail>(`${COMMANDES}.update_commande`, { name: commande.name, modified: commande.modified, values }, true)
export const runCommandeAction = (commande: CommandeDetail, action: 'valider' | 'annuler') =>
	call<CommandeDetail>(`${COMMANDES}.${action === 'valider' ? 'validate_commande' : 'cancel_commande'}`, { name: commande.name, modified: commande.modified }, true)
export const deleteCommande = (commande: CommandeDetail) => call<{ deleted: string }>(`${COMMANDES}.delete_commande`, { name: commande.name, modified: commande.modified }, true)
export const setCommandeStatus = (commande: CommandeDetail, action: StatusAction) => call<CommandeDetail>(`${COMMANDES}.set_commande_status`, { name: commande.name, modified: commande.modified, action }, true)
export const createSuivante = (commande: CommandeDetail, kind: 'livraison' | 'facture') =>
	call<{ doctype: string; name: string; commande: CommandeDetail }>(`${COMMANDES}.create_suivante`, { name: commande.name, modified: commande.modified, kind }, true)

export const commandePrintUrl = (name: string) => `/printview?doctype=Sales%20Order&name=${encodeURIComponent(name)}&trigger_print=1`
export const commandePdfUrl = (name: string) => `/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name=${encodeURIComponent(name)}`

/** Commentaires et activité d'une commande, pour le fil commun. */
export function commandeActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${COMMANDES}.get_commande_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${COMMANDES}.add_commande_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${COMMANDES}.update_commande_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${COMMANDES}.delete_commande_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Bons de livraison : liste, aperçu, fiche, préparation (dépôt, lot, quantité) et cycle. */
const LIVRAISONS = 'unicare.api.bureau_livraisons'

export const getLivraisons = (view: LivraisonView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<LivraisonsResponse>(`${LIVRAISONS}.get_livraisons`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getLivraison = (name: string) => call<LivraisonDetail>(`${LIVRAISONS}.get_livraison`, { name })
export const getLivraisonOptions = () => call<{ filter_fields?: FilterField[] }>(`${LIVRAISONS}.get_livraison_options`)
export const prepareLivraison = (livraison: LivraisonDetail, lignes: { name: string; quantite?: number; depot?: string; lot?: string }[], transport?: string, vehicule?: string) =>
	call<LivraisonDetail>(`${LIVRAISONS}.prepare_livraison`, { name: livraison.name, modified: livraison.modified, lignes, transport, vehicule }, true)
export const runLivraisonAction = (livraison: LivraisonDetail, action: 'valider' | 'annuler') =>
	call<LivraisonDetail>(`${LIVRAISONS}.${action === 'valider' ? 'validate_livraison' : 'cancel_livraison'}`, { name: livraison.name, modified: livraison.modified }, true)
export const deleteLivraison = (livraison: LivraisonDetail) => call<{ deleted: string }>(`${LIVRAISONS}.delete_livraison`, { name: livraison.name, modified: livraison.modified }, true)
export const createLivraisonSuivante = (livraison: LivraisonDetail, kind: 'facture' | 'retour') =>
	call<{ doctype: string; name: string; livraison: LivraisonDetail }>(`${LIVRAISONS}.create_suivante`, { name: livraison.name, modified: livraison.modified, kind }, true)

export const livraisonPrintUrl = (name: string) => `/printview?doctype=Delivery%20Note&name=${encodeURIComponent(name)}&trigger_print=1`
export const livraisonPdfUrl = (name: string) => `/api/method/frappe.utils.print_format.download_pdf?doctype=Delivery%20Note&name=${encodeURIComponent(name)}`

/** Commentaires et activité d'un bon de livraison, pour le fil commun. */
export function livraisonActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${LIVRAISONS}.get_livraison_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${LIVRAISONS}.add_livraison_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${LIVRAISONS}.update_livraison_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${LIVRAISONS}.delete_livraison_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Factures : liste, aperçu, fiche, encaissement, avoirs et cycle. */
const FACTURES = 'unicare.api.bureau_factures'

export const getFactures = (view: FactureView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<FacturesResponse>(`${FACTURES}.get_factures`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getFacture = (name: string) => call<FactureDetail>(`${FACTURES}.get_facture`, { name })
export const getFactureOptions = () => call<FactureOptions>(`${FACTURES}.get_facture_options`)
export const updateFacture = (facture: FactureDetail, values: { echeance?: string; taxes?: string; lignes?: { name: string; quantite: number }[] }) =>
	call<FactureDetail>(`${FACTURES}.update_facture`, { name: facture.name, modified: facture.modified, ...values }, true)
export const runFactureAction = (facture: FactureDetail, action: 'valider' | 'annuler') =>
	call<FactureDetail>(`${FACTURES}.${action === 'valider' ? 'validate_facture' : 'cancel_facture'}`, { name: facture.name, modified: facture.modified }, true)
export const deleteFacture = (facture: FactureDetail) => call<{ deleted: string }>(`${FACTURES}.delete_facture`, { name: facture.name, modified: facture.modified }, true)
export const encaisserFacture = (facture: FactureDetail, values: { montant: number; mode: string; date: string; reference?: string; date_reference?: string }) =>
	call<{ paiement: string; facture: FactureDetail }>(`${FACTURES}.encaisser`, { name: facture.name, modified: facture.modified, ...values }, true)
export const createAvoir = (facture: FactureDetail) => call<{ name: string; facture: FactureDetail }>(`${FACTURES}.create_avoir`, { name: facture.name, modified: facture.modified }, true)

export const facturePrintUrl = (name: string) => `/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(name)}&trigger_print=1`
export const facturePdfUrl = (name: string) => `/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=${encodeURIComponent(name)}`

/** Commentaires et activité d'une facture, pour le fil commun. */
export function factureActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${FACTURES}.get_facture_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${FACTURES}.add_facture_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${FACTURES}.update_facture_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${FACTURES}.delete_facture_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Paiements : liste, aperçu, fiche et assistant (type, tiers, montant, rapprochement). */
const PAIEMENTS = 'unicare.api.bureau_paiements'

export const getPaiements = (view: PaiementView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<PaiementsResponse>(`${PAIEMENTS}.get_paiements`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getPaiement = (name: string) => call<PaiementDetail>(`${PAIEMENTS}.get_paiement`, { name })
export const getPaiementOptions = () => call<PaiementOptions>(`${PAIEMENTS}.get_paiement_options`)
export const searchTiers = (type: PaiementType, search: string) => call<{ name: string; label: string }[]>(`${PAIEMENTS}.search_tiers`, { kind: type, search: search.trim() || undefined })
export const getPiecesOuvertes = (type: PaiementType, tiers: string, exclude?: string) => call<PieceOuverte[]>(`${PAIEMENTS}.get_pieces_ouvertes`, { kind: type, tiers, exclude })

export interface PaiementValues {
	type: PaiementType
	tiers: string
	montant: number
	mode: string
	date: string
	reference?: string
	date_reference?: string
	remarque?: string
	affectations: { name: string; montant: number }[]
}
export const createPaiement = (values: PaiementValues) => call<{ name: string }>(`${PAIEMENTS}.create_paiement`, { values }, true)
export const updatePaiement = (paiement: PaiementDetail, values: PaiementValues) => call<PaiementDetail>(`${PAIEMENTS}.update_paiement`, { name: paiement.name, modified: paiement.modified, values }, true)
export const runPaiementAction = (paiement: PaiementDetail, action: 'valider' | 'annuler') =>
	call<PaiementDetail>(`${PAIEMENTS}.${action === 'valider' ? 'validate_paiement' : 'cancel_paiement'}`, { name: paiement.name, modified: paiement.modified }, true)
export const deletePaiement = (paiement: PaiementDetail) => call<{ deleted: string }>(`${PAIEMENTS}.delete_paiement`, { name: paiement.name, modified: paiement.modified }, true)

export const paiementPrintUrl = (name: string) => `/printview?doctype=Payment%20Entry&name=${encodeURIComponent(name)}&trigger_print=1`
export const paiementPdfUrl = (name: string) => `/api/method/frappe.utils.print_format.download_pdf?doctype=Payment%20Entry&name=${encodeURIComponent(name)}`

/** Commentaires et activité d'un paiement, pour le fil commun. */
export function paiementActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${PAIEMENTS}.get_paiement_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${PAIEMENTS}.add_paiement_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${PAIEMENTS}.update_paiement_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${PAIEMENTS}.delete_paiement_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Pièces d'achat : articles d'achat proposés dans les fenêtres. */
const ACHATS = 'unicare.api.bureau_achats'
export const searchAchatArticles = (search: string) => call<AchatArticleChoice[]>(`${ACHATS}.search_achat_articles`, { search: search.trim() || undefined })

/** Devis fournisseur : liste, aperçu, fiche, création et cycle (valider, commande d'achat, annuler). */
const DEVIS_F = 'unicare.api.bureau_devis_fournisseur'

export const getDevisFournisseurs = (view: DevisFournisseurView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<DevisFournisseurResponse>(`${DEVIS_F}.get_devis_fournisseurs`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getDevisFournisseur = (name: string) => call<DevisFournisseurDetail>(`${DEVIS_F}.get_devis_fournisseur`, { name })
export const getDevisFournisseurOptions = () => call<DevisFournisseurOptions>(`${DEVIS_F}.get_devis_fournisseur_options`)

export interface DevisFournisseurValues {
	fournisseur?: string
	valable?: string
	reference?: string
	taxes?: string
	lignes?: AchatLineValues[]
}
export const createDevisFournisseur = (values: DevisFournisseurValues) => call<{ name: string }>(`${DEVIS_F}.create_devis_fournisseur`, { values }, true)
export const updateDevisFournisseur = (devis: DevisFournisseurDetail, values: DevisFournisseurValues) =>
	call<DevisFournisseurDetail>(`${DEVIS_F}.update_devis_fournisseur`, { name: devis.name, modified: devis.modified, values }, true)
const DEVIS_F_METHODS = { valider: 'validate_devis_fournisseur', annuler: 'cancel_devis_fournisseur' } as const
export const runDevisFournisseurAction = (devis: DevisFournisseurDetail, action: 'valider' | 'annuler') =>
	call<DevisFournisseurDetail>(`${DEVIS_F}.${DEVIS_F_METHODS[action]}`, { name: devis.name, modified: devis.modified }, true)
export const deleteDevisFournisseur = (devis: DevisFournisseurDetail) => call<{ deleted: string }>(`${DEVIS_F}.delete_devis_fournisseur`, { name: devis.name, modified: devis.modified }, true)
export const createDevisFournisseurCommande = (devis: DevisFournisseurDetail, reception: string) =>
	call<{ commande: string; note: string | null; devis: DevisFournisseurDetail }>(`${DEVIS_F}.create_commande_achat`, { name: devis.name, modified: devis.modified, reception }, true)
export const devisFournisseurPrintUrl = (name: string) => `/printview?doctype=Supplier%20Quotation&name=${encodeURIComponent(name)}&trigger_print=1`

export function devisFournisseurActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${DEVIS_F}.get_devis_fournisseur_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${DEVIS_F}.add_devis_fournisseur_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${DEVIS_F}.update_devis_fournisseur_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${DEVIS_F}.delete_devis_fournisseur_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Commandes d'achat : liste, aperçu, fiche, création et cycle (valider, réception, facture, statuts, annuler). */
const COMMANDES_ACHAT = 'unicare.api.bureau_commandes_achat'

export const getCommandesAchat = (view: CommandeAchatView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<CommandesAchatResponse>(`${COMMANDES_ACHAT}.get_commandes_achat`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getCommandeAchat = (name: string) => call<CommandeAchatDetail>(`${COMMANDES_ACHAT}.get_commande_achat`, { name })
export const getCommandeAchatOptions = () => call<CommandeAchatOptions>(`${COMMANDES_ACHAT}.get_commande_achat_options`)

export interface CommandeAchatValues {
	fournisseur?: string
	reception?: string
	taxes?: string
	lignes?: AchatLineValues[]
}
export const createCommandeAchat = (values: CommandeAchatValues) => call<{ name: string }>(`${COMMANDES_ACHAT}.create_commande_achat`, { values }, true)
export const updateCommandeAchat = (commande: CommandeAchatDetail, values: CommandeAchatValues) =>
	call<CommandeAchatDetail>(`${COMMANDES_ACHAT}.update_commande_achat`, { name: commande.name, modified: commande.modified, values }, true)
export const runCommandeAchatAction = (commande: CommandeAchatDetail, action: 'valider' | 'annuler') =>
	call<CommandeAchatDetail>(`${COMMANDES_ACHAT}.${action === 'valider' ? 'validate_commande_achat' : 'cancel_commande_achat'}`, { name: commande.name, modified: commande.modified }, true)
export const deleteCommandeAchat = (commande: CommandeAchatDetail) => call<{ deleted: string }>(`${COMMANDES_ACHAT}.delete_commande_achat`, { name: commande.name, modified: commande.modified }, true)
export const setCommandeAchatStatus = (commande: CommandeAchatDetail, action: StatusAction) =>
	call<CommandeAchatDetail>(`${COMMANDES_ACHAT}.set_commande_achat_status`, { name: commande.name, modified: commande.modified, action }, true)
export const createCommandeAchatSuivante = (commande: CommandeAchatDetail, kind: 'reception' | 'facture') =>
	call<{ doctype: string; name: string; note: string | null; commande: CommandeAchatDetail }>(`${COMMANDES_ACHAT}.create_suivante`, { name: commande.name, modified: commande.modified, kind }, true)
export const commandeAchatPrintUrl = (name: string) => `/printview?doctype=Purchase%20Order&name=${encodeURIComponent(name)}&trigger_print=1`
export const commandeAchatPdfUrl = (name: string) => `/api/method/frappe.utils.print_format.download_pdf?doctype=Purchase%20Order&name=${encodeURIComponent(name)}`

export function commandeAchatActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${COMMANDES_ACHAT}.get_commande_achat_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${COMMANDES_ACHAT}.add_commande_achat_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${COMMANDES_ACHAT}.update_commande_achat_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${COMMANDES_ACHAT}.delete_commande_achat_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Réceptions : liste, aperçu, fiche, préparation (quantité, dépôt, lot fournisseur) et cycle. */
const RECEPTIONS = 'unicare.api.bureau_receptions'

export const getReceptions = (view: ReceptionView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<ReceptionsResponse>(`${RECEPTIONS}.get_receptions`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getReception = (name: string) => call<ReceptionDetail>(`${RECEPTIONS}.get_reception`, { name })
export const getReceptionOptions = () => call<{ filter_fields?: FilterField[] }>(`${RECEPTIONS}.get_reception_options`)
export const prepareReception = (reception: ReceptionDetail, lignes: ReceptionPrepChange[], blFournisseur?: string, transport?: string) =>
	call<ReceptionDetail>(`${RECEPTIONS}.prepare_reception`, { name: reception.name, modified: reception.modified, lignes, bl_fournisseur: blFournisseur, transport }, true)
export const runReceptionAction = (reception: ReceptionDetail, action: 'valider' | 'annuler') =>
	call<ReceptionDetail>(`${RECEPTIONS}.${action === 'valider' ? 'validate_reception' : 'cancel_reception'}`, { name: reception.name, modified: reception.modified }, true)
export const deleteReception = (reception: ReceptionDetail) => call<{ deleted: string }>(`${RECEPTIONS}.delete_reception`, { name: reception.name, modified: reception.modified }, true)
export const createReceptionSuivante = (reception: ReceptionDetail, kind: 'facture' | 'retour') =>
	call<{ doctype: string; name: string; note: string | null; reception: ReceptionDetail }>(`${RECEPTIONS}.create_suivante`, { name: reception.name, modified: reception.modified, kind }, true)
export const receptionPrintUrl = (name: string) => `/printview?doctype=Purchase%20Receipt&name=${encodeURIComponent(name)}&trigger_print=1`

export function receptionActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${RECEPTIONS}.get_reception_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${RECEPTIONS}.add_reception_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${RECEPTIONS}.update_reception_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${RECEPTIONS}.delete_reception_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Factures d'achat : liste, aperçu, fiche, paiement au fournisseur, avoirs et cycle. */
const FACTURES_ACHAT = 'unicare.api.bureau_factures_achat'

export const getFacturesAchat = (view: FactureAchatView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<FacturesAchatResponse>(`${FACTURES_ACHAT}.get_factures_achat`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getFactureAchat = (name: string) => call<FactureAchatDetail>(`${FACTURES_ACHAT}.get_facture_achat`, { name })
export const getFactureAchatOptions = () => call<FactureAchatOptions>(`${FACTURES_ACHAT}.get_facture_achat_options`)
export const updateFactureAchat = (facture: FactureAchatDetail, values: FactureAchatValues) =>
	call<FactureAchatDetail>(`${FACTURES_ACHAT}.update_facture_achat`, { name: facture.name, modified: facture.modified, values }, true)
export const runFactureAchatAction = (facture: FactureAchatDetail, action: 'valider' | 'annuler') =>
	call<FactureAchatDetail>(`${FACTURES_ACHAT}.${action === 'valider' ? 'validate_facture_achat' : 'cancel_facture_achat'}`, { name: facture.name, modified: facture.modified }, true)
export const deleteFactureAchat = (facture: FactureAchatDetail) => call<{ deleted: string }>(`${FACTURES_ACHAT}.delete_facture_achat`, { name: facture.name, modified: facture.modified }, true)
export const payerFactureAchat = (facture: FactureAchatDetail, values: { montant: number; mode: string; date: string; reference?: string; date_reference?: string }) =>
	call<{ paiement: string; facture: FactureAchatDetail }>(`${FACTURES_ACHAT}.payer`, { name: facture.name, modified: facture.modified, ...values }, true)
export const createAvoirFournisseur = (facture: FactureAchatDetail) => call<{ name: string; note: string | null; facture: FactureAchatDetail }>(`${FACTURES_ACHAT}.create_avoir`, { name: facture.name, modified: facture.modified }, true)
export const factureAchatPrintUrl = (name: string) => `/printview?doctype=Purchase%20Invoice&name=${encodeURIComponent(name)}&trigger_print=1`

export function factureAchatActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${FACTURES_ACHAT}.get_facture_achat_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${FACTURES_ACHAT}.add_facture_achat_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${FACTURES_ACHAT}.update_facture_achat_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${FACTURES_ACHAT}.delete_facture_achat_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** Nouvelle version (brouillon `NOM-1`) d'une pièce annulée, comme « Modifier » sur le Desk. */
export const createPieceVersion = (module: VersionModule, piece: { name: string; modified: string }) =>
	call<{ name: string; note: string | null }>(`unicare.api.bureau_${module}.create_version`, { name: piece.name, modified: piece.modified }, true)

/** Suppression d'une fiche non validable : Frappe refuse tant qu'une pièce y est liée. */
export const deleteClient = (client: { name: string; modified: string }) => call<{ deleted: string }>(`${CLIENTS}.delete_client`, { name: client.name, modified: client.modified }, true)
export const deleteFournisseur = (fournisseur: { name: string; modified: string }) =>
	call<{ deleted: string }>(`${FOURNISSEURS}.delete_fournisseur`, { name: fournisseur.name, modified: fournisseur.modified }, true)
export const deleteArticle = (article: { name: string; modified: string }) => call<{ deleted: string }>(`${ARTICLES}.delete_article`, { name: article.name, modified: article.modified }, true)

/** Dépôts : liste, aperçu, fiche, création, modification et suppression. */
const DEPOTS = 'unicare.api.bureau_depots'

export const getDepots = (view: DepotView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<DepotsResponse>(`${DEPOTS}.get_depots`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getDepot = (name: string) => call<DepotDetail>(`${DEPOTS}.get_depot`, { name })
export const getDepotFiche = (name: string) => call<DepotDetail>(`${DEPOTS}.get_depot`, { name, full: 1 })
export const getDepotOptions = () => call<DepotOptions>(`${DEPOTS}.get_depot_options`)
export const createDepot = (values: DepotValues) => call<{ name: string }>(`${DEPOTS}.create_depot`, { values }, true)
export const updateDepot = (depot: DepotDetail, values: DepotValues) => call<DepotDetail>(`${DEPOTS}.update_depot`, { name: depot.name, modified: depot.modified, values }, true)
export const deleteDepot = (depot: { name: string; modified: string }) => call<{ deleted: string }>(`${DEPOTS}.delete_depot`, { name: depot.name, modified: depot.modified }, true)

export function depotActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${DEPOTS}.get_depot_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${DEPOTS}.add_depot_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${DEPOTS}.update_depot_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${DEPOTS}.delete_depot_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}

/** État du stock : une ligne par article et par dépôt, en lecture seule, et son historique. */
const ETAT_STOCK = 'unicare.api.bureau_etat_stock'

export const getEtatStock = (view: EtatStockView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<EtatStockResponse>(`${ETAT_STOCK}.get_etat_stock`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getEtatStockOptions = () => call<EtatStockOptions>(`${ETAT_STOCK}.get_etat_stock_options`)
export const getLigneStock = (name: string) => call<LigneStockDetail>(`${ETAT_STOCK}.get_ligne_stock`, { name })
export const getLigneStockFiche = (name: string) => call<LigneStockDetail>(`${ETAT_STOCK}.get_ligne_stock`, { name, full: 1 })

/** Lots : liste, aperçu, fiche (stock par dépôt, mouvements, traçabilité), modification et suppression. */
const LOTS = 'unicare.api.bureau_lots'

export const getLots = (view: LotView, conditions: Condition[], search: string, paging: ListPaging = {}) =>
	call<LotsResponse>(`${LOTS}.get_lots`, {
		view,
		conditions: conditionsForServer(conditions),
		search: search.trim() || undefined,
		start: paging.start,
		page_length: paging.pageLength,
		sort: paging.sort,
		direction: paging.direction,
	})
export const getLot = (name: string) => call<LotDetail>(`${LOTS}.get_lot`, { name })
export const getLotFiche = (name: string) => call<LotDetail>(`${LOTS}.get_lot`, { name, full: 1 })
export const getLotOptions = () => call<LotOptions>(`${LOTS}.get_lot_options`)
export const updateLot = (lot: LotDetail, values: LotValues) => call<LotDetail>(`${LOTS}.update_lot`, { name: lot.name, modified: lot.modified, values }, true)
export const deleteLot = (lot: { name: string; modified: string }) => call<{ deleted: string }>(`${LOTS}.delete_lot`, { name: lot.name, modified: lot.modified }, true)

export function lotActivity(name: string): ActivityApi {
	return {
		load: () => call<ActivityFeedData>(`${LOTS}.get_lot_activity`, { name }),
		add: (text, mentions) => call<ActivityFeedData>(`${LOTS}.add_lot_comment`, { name, text, mentions }, true),
		update: (comment, text, mentions) => call<ActivityFeedData>(`${LOTS}.update_lot_comment`, { name, comment, text, mentions }, true),
		remove: (comment) => call<ActivityFeedData>(`${LOTS}.delete_lot_comment`, { name, comment }, true),
		mentionCandidates: () => call<Mention[]>(`${CLIENTS}.get_mention_candidates`),
	}
}
