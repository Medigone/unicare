(() => {
	"use strict";

	document.documentElement.classList.add("reveal-ready");

	const header = document.querySelector("[data-header]");
	const menuButton = document.querySelector(".menu-toggle");
	const mobileMenu = document.querySelector("#mobile-menu");
	const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

	const closeMenu = () => {
		if (!menuButton || !mobileMenu) return;
		menuButton.setAttribute("aria-expanded", "false");
		menuButton.setAttribute("aria-label", "Ouvrir le menu");
		mobileMenu.hidden = true;
		document.body.classList.remove("menu-open");
	};

	if (menuButton && mobileMenu) {
		menuButton.addEventListener("click", () => {
			const willOpen = menuButton.getAttribute("aria-expanded") !== "true";
			menuButton.setAttribute("aria-expanded", String(willOpen));
			menuButton.setAttribute("aria-label", willOpen ? "Fermer le menu" : "Ouvrir le menu");
			mobileMenu.hidden = !willOpen;
			document.body.classList.toggle("menu-open", willOpen);
		});

		mobileMenu.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
		document.addEventListener("keydown", (event) => {
			if (event.key === "Escape") {
				closeMenu();
				menuButton.focus();
			}
		});
		window.addEventListener("resize", () => {
			if (window.innerWidth > 860) closeMenu();
		});
	}

	const updateHeader = () => header?.classList.toggle("is-scrolled", window.scrollY > 10);
	updateHeader();
	window.addEventListener("scroll", updateHeader, { passive: true });

	const revealItems = document.querySelectorAll(".reveal");
	if (reduceMotion || !("IntersectionObserver" in window)) {
		revealItems.forEach((item) => item.classList.add("is-visible"));
	} else {
		const revealObserver = new IntersectionObserver(
			(entries, observer) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						entry.target.classList.add("is-visible");
						observer.unobserve(entry.target);
					}
				});
			},
			{ rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
		);
		revealItems.forEach((item) => revealObserver.observe(item));
		window.setTimeout(() => {
			revealItems.forEach((item) => item.classList.add("is-visible"));
		}, 800);
	}

	document.querySelectorAll(".faq-item button").forEach((button) => {
		button.addEventListener("click", () => {
			const panelId = button.getAttribute("aria-controls");
			const panel = document.getElementById(panelId);
			const isOpen = button.getAttribute("aria-expanded") === "true";
			button.setAttribute("aria-expanded", String(!isOpen));
			if (panel) panel.hidden = isOpen;
		});
	});
})();
