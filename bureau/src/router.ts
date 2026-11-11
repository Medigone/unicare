import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import ArticlesPage from './pages/ArticlesPage.vue'
import ClientsPage from './pages/ClientsPage.vue'
import DepotsPage from './pages/DepotsPage.vue'
import EtatStockPage from './pages/EtatStockPage.vue'
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
import LoginPage from './pages/LoginPage.vue'

// Chaque page reprise ajoute sa route avec `meta.doctype` : App.vue affiche un refus si le rôle ne lit pas ce document.
export const routes: RouteRecordRaw[] = [
	// Seule page servie sans session : hors de la coquille.
	{ path: '/connexion', name: 'Login', component: LoginPage },
	{ path: '/', name: 'Home', component: HomePage },
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
	{ path: '/depots', name: 'Depots', component: DepotsPage, meta: { doctype: 'Warehouse' } },
	{ path: '/depots/:id', name: 'Depot', component: DepotsPage, props: true, meta: { doctype: 'Warehouse' } },
	{ path: '/paiements', name: 'Paiements', component: PaiementsPage, meta: { doctype: 'Payment Entry' } },
	{ path: '/paiements/:id', name: 'PaiementFiche', component: PaiementsPage, props: true, meta: { doctype: 'Payment Entry' } },
	{ path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory('/bureau'), routes })

router.beforeEach((to) => {
	if (to.name === 'Login' && window.user) return { name: 'Home' }
})

export default router
