import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import ArticlesPage from './pages/ArticlesPage.vue'
import ClientsPage from './pages/ClientsPage.vue'
import DepotsPage from './pages/DepotsPage.vue'
import EtatStockPage from './pages/EtatStockPage.vue'
import LotsPage from './pages/LotsPage.vue'
import InventairesPage from './pages/InventairesPage.vue'
import MouvementsPage from './pages/MouvementsPage.vue'
import OrdresPage from './pages/OrdresPage.vue'
import RecettesPage from './pages/RecettesPage.vue'
import ReglagesProductionPage from './pages/ReglagesProductionPage.vue'
import FournisseursPage from './pages/FournisseursPage.vue'
import CommandesPage from './pages/CommandesPage.vue'
import CommandesAchatPage from './pages/CommandesAchatPage.vue'
import DevisPage from './pages/DevisPage.vue'
import DevisFournisseursPage from './pages/DevisFournisseursPage.vue'
import FacturesPage from './pages/FacturesPage.vue'
import FacturesAchatPage from './pages/FacturesAchatPage.vue'
import LivraisonsPage from './pages/LivraisonsPage.vue'
import ReceptionsPage from './pages/ReceptionsPage.vue'
import PaiementsPage from './pages/PaiementsPage.vue'
import HomePage from './pages/HomePage.vue'
import TableauPage from './pages/TableauPage.vue'
import LoginPage from './pages/LoginPage.vue'

// Chaque page reprise ajoute sa route avec `meta.doctype` : App.vue affiche un refus si le rôle ne lit pas ce document.
export const routes: RouteRecordRaw[] = [
	// Seule page servie sans session : hors de la coquille.
	{ path: '/connexion', name: 'Login', component: LoginPage },
	{ path: '/', name: 'Home', component: HomePage },
	// Tableaux de bord des modules : chaque bloc n'est envoyé que si le rôle lit ses documents (bureau_tableaux.py).
	{ path: '/tableau-de-bord/ventes', name: 'TableauVentes', component: TableauPage, props: { module: 'ventes' } },
	{ path: '/tableau-de-bord/achats', name: 'TableauAchats', component: TableauPage, props: { module: 'achats' } },
	{ path: '/tableau-de-bord/stock', name: 'TableauStock', component: TableauPage, props: { module: 'stock' } },
	{ path: '/tableau-de-bord/tresorerie', name: 'TableauTresorerie', component: TableauPage, props: { module: 'tresorerie' } },
	{ path: '/clients', name: 'Clients', component: ClientsPage, meta: { doctype: 'Customer' } },
	{ path: '/clients/:id', name: 'Client', component: ClientsPage, props: true, meta: { doctype: 'Customer' } },
	{ path: '/fournisseurs', name: 'Fournisseurs', component: FournisseursPage, meta: { doctype: 'Supplier' } },
	{ path: '/fournisseurs/:id', name: 'Fournisseur', component: FournisseursPage, props: true, meta: { doctype: 'Supplier' } },
	{ path: '/articles', name: 'Articles', component: ArticlesPage, meta: { doctype: 'Item' } },
	{ path: '/articles/:id', name: 'Article', component: ArticlesPage, props: true, meta: { doctype: 'Item' } },
	{ path: '/devis', name: 'DevisListe', component: DevisPage, meta: { doctype: 'Quotation' } },
	{ path: '/devis/:id', name: 'DevisFiche', component: DevisPage, props: true, meta: { doctype: 'Quotation' } },
	{ path: '/commandes', name: 'Commandes', component: CommandesPage, meta: { doctype: 'Sales Order' } },
	{ path: '/commandes/:id', name: 'CommandeFiche', component: CommandesPage, props: true, meta: { doctype: 'Sales Order' } },
	{ path: '/livraisons', name: 'Livraisons', component: LivraisonsPage, meta: { doctype: 'Delivery Note' } },
	{ path: '/livraisons/:id', name: 'LivraisonFiche', component: LivraisonsPage, props: true, meta: { doctype: 'Delivery Note' } },
	{ path: '/factures', name: 'Factures', component: FacturesPage, meta: { doctype: 'Sales Invoice' } },
	{ path: '/factures/:id', name: 'FactureFiche', component: FacturesPage, props: true, meta: { doctype: 'Sales Invoice' } },
	{ path: '/devis-fournisseurs', name: 'DevisFournisseurListe', component: DevisFournisseursPage, meta: { doctype: 'Supplier Quotation' } },
	{ path: '/devis-fournisseurs/:id', name: 'DevisFournisseurFiche', component: DevisFournisseursPage, props: true, meta: { doctype: 'Supplier Quotation' } },
	{ path: '/commandes-achat', name: 'CommandesAchat', component: CommandesAchatPage, meta: { doctype: 'Purchase Order' } },
	{ path: '/commandes-achat/:id', name: 'CommandeAchatFiche', component: CommandesAchatPage, props: true, meta: { doctype: 'Purchase Order' } },
	{ path: '/receptions', name: 'Receptions', component: ReceptionsPage, meta: { doctype: 'Purchase Receipt' } },
	{ path: '/receptions/:id', name: 'ReceptionFiche', component: ReceptionsPage, props: true, meta: { doctype: 'Purchase Receipt' } },
	{ path: '/factures-achat', name: 'FacturesAchat', component: FacturesAchatPage, meta: { doctype: 'Purchase Invoice' } },
	{ path: '/factures-achat/:id', name: 'FactureAchatFiche', component: FacturesAchatPage, props: true, meta: { doctype: 'Purchase Invoice' } },
	{ path: '/stock', name: 'EtatStock', component: EtatStockPage, meta: { doctype: 'Bin' } },
	{ path: '/stock/:id', name: 'LigneStock', component: EtatStockPage, props: true, meta: { doctype: 'Bin' } },
	{ path: '/mouvements', name: 'Mouvements', component: MouvementsPage, meta: { doctype: 'Stock Entry' } },
	{ path: '/mouvements/:id', name: 'MouvementFiche', component: MouvementsPage, props: true, meta: { doctype: 'Stock Entry' } },
	{ path: '/inventaires', name: 'Inventaires', component: InventairesPage, meta: { doctype: 'Stock Reconciliation' } },
	{ path: '/inventaires/:id', name: 'InventaireFiche', component: InventairesPage, props: true, meta: { doctype: 'Stock Reconciliation' } },
	{ path: '/lots', name: 'Lots', component: LotsPage, meta: { doctype: 'Batch' } },
	{ path: '/lots/:id', name: 'Lot', component: LotsPage, props: true, meta: { doctype: 'Batch' } },
	{ path: '/depots', name: 'Depots', component: DepotsPage, meta: { doctype: 'Warehouse' } },
	{ path: '/depots/:id', name: 'Depot', component: DepotsPage, props: true, meta: { doctype: 'Warehouse' } },
	{ path: '/ordres', name: 'Ordres', component: OrdresPage, meta: { doctype: 'Ordre de Conditionnement' } },
	{ path: '/ordres/:id', name: 'OrdreFiche', component: OrdresPage, props: true, meta: { doctype: 'Ordre de Conditionnement' } },
	{ path: '/recettes', name: 'Recettes', component: RecettesPage, meta: { doctype: 'Recette de Conditionnement' } },
	{ path: '/recettes/:id', name: 'RecetteFiche', component: RecettesPage, props: true, meta: { doctype: 'Recette de Conditionnement' } },
	{ path: '/reglages-production', name: 'ReglagesProduction', component: ReglagesProductionPage, meta: { doctype: 'Checklist Ordre Conditionnement' } },
	{ path: '/paiements', name: 'Paiements', component: PaiementsPage, meta: { doctype: 'Payment Entry' } },
	{ path: '/paiements/:id', name: 'PaiementFiche', component: PaiementsPage, props: true, meta: { doctype: 'Payment Entry' } },
	{ path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory('/bureau'), routes })

router.beforeEach((to) => {
	if (to.name === 'Login' && window.user) return { name: 'Home' }
})

export default router
