/**
 * Viewport-entry reveal.
 *
 * Components opt in by calling `reveal(this)` at the end of their
 * `connectedCallback`. The helper sets `data-rd-reveal` immediately (so
 * CSS can hide / offset the element) and `data-rd-revealed` once the
 * element scrolls into view. A single shared `IntersectionObserver` is
 * used across all components.
 *
 * Elements that are direct children of `<rd-page>` skip the IO step —
 * the page-enter cascade in `components/page` already handles them, and
 * stacking both effects would double-animate first-fold content.
 */

const onRevealCallbacks = new WeakMap<Element, () => void>();
let revealObserver: IntersectionObserver | null = null;

function getRevealObserver(): IntersectionObserver {
	if (revealObserver) return revealObserver;
	revealObserver = new IntersectionObserver(
		(entries) => {
			for (const entry of entries) {
				if (!entry.isIntersecting) continue;
				entry.target.setAttribute("data-rd-revealed", "");
				revealObserver?.unobserve(entry.target);
				const cb = onRevealCallbacks.get(entry.target);
				if (cb) {
					onRevealCallbacks.delete(entry.target);
					try {
						cb();
					} catch (err) {
						console.warn("[richdoc] reveal callback failed", err);
					}
				}
			}
		},
		{ rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
	);
	return revealObserver;
}

export function reveal(el: HTMLElement, onReveal?: () => void): void {
	// Direct children of <rd-page> are owned by the page-enter cascade.
	if (el.parentElement?.tagName === "RD-PAGE") {
		el.setAttribute("data-rd-revealed", "");
		if (onReveal) {
			// Run on next frame so any layout the cascade triggers settles first.
			requestAnimationFrame(() => onReveal());
		}
		return;
	}
	if (typeof IntersectionObserver === "undefined") {
		el.setAttribute("data-rd-revealed", "");
		if (onReveal) onReveal();
		return;
	}
	el.setAttribute("data-rd-reveal", "");
	if (onReveal) onRevealCallbacks.set(el, onReveal);
	getRevealObserver().observe(el);
}
