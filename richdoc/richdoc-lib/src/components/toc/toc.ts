import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { slugify } from "../../lib/text.ts";
import { spec, tagName } from "./toc.schema.ts";

/* rd-toc — floating, sticky table of contents.
 *
 * Lifecycle:
 *   1. _build()        Walk <rd-page> headings, build the entry list, ensure
 *                      every indexed heading has an id.
 *   2. _mount()        Render the shared markup: rail (wide), bar + popover
 *                      (narrow). Both presentations are always in the DOM;
 *                      CSS decides which is visible.
 *   3. _observe()      IntersectionObserver tracks which heading is active.
 *                      The most recently passed heading wins.
 *   4. _observeHero()  In narrow mode, the bar fades in only after <rd-hero>
 *                      (or the first <rd-page> child) scrolls out of view.
 *   5. scroll + rAF    Updates --rd-toc-progress for the rail / bar fill.
 *
 * The host element is `display: contents`; the rail, bar and popover are
 * the actual painted children. The page.css :has(rd-toc) grid rule flips
 * the host to `display: block` at the breakpoint so the rail has a
 * sticking context.
 */

interface TocEntry {
	id: string;
	heading: HTMLElement;
	anchor: HTMLAnchorElement;
	level: number;
}

/** Chevron-down icon, drawn inline so we don't pull in <rd-icon>'s CDN
 *  fetch for a single static glyph that's always visible. */
const CHEVRON_DOWN_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
	stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
	aria-hidden="true" focusable="false"><path d="M6 9l6 6 6-6"/></svg>`;

class RdToc extends HTMLElement implements Upgradeable {
	_upgraded = false;

	private _entries: TocEntry[] = [];
	private _activeId: string | null = null;
	private _headingIo?: IntersectionObserver;
	private _heroIo?: IntersectionObserver;
	private _rafPending = false;
	private _docMaxScroll = 0;
	private _prefersReducedMotion = false;
	private _rail: HTMLElement | null = null;
	private _railList: HTMLElement | null = null;
	private _bar: HTMLElement | null = null;
	private _barCurrent: HTMLElement | null = null;
	private _pop: HTMLElement | null = null;
	private _popList: HTMLElement | null = null;
	private _onScroll = (): void => this._scheduleProgressUpdate();
	private _onResize = (): void => {
		this._recomputeDocMax();
		this._updateProgress();
	};
	private _onDocClick = (ev: MouseEvent): void => {
		if (this.dataset.rdTocOpen !== "true") return;
		const t = ev.target as Node | null;
		if (t && (this._bar?.contains(t) || this._pop?.contains(t))) return;
		this._setOpen(false);
	};
	private _onKey = (ev: KeyboardEvent): void => {
		if (ev.key === "Escape" && this.dataset.rdTocOpen === "true") {
			this._setOpen(false);
		}
	};

	connectedCallback(): void {
		if (this._upgraded) return;
		this._upgraded = true;
		this._prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		// Defer one tick so siblings (rd-hero, rd-section, …) have a chance
		// to upgrade and write their final headings.
		queueMicrotask(() => this._init());
	}

	disconnectedCallback(): void {
		this._headingIo?.disconnect();
		this._heroIo?.disconnect();
		window.removeEventListener("scroll", this._onScroll);
		window.removeEventListener("resize", this._onResize);
		document.removeEventListener("click", this._onDocClick, true);
		document.removeEventListener("keydown", this._onKey);
	}

	// ─── Initialisation ──────────────────────────────────────────────────

	private _init(): void {
		this._build();
		if (this._entries.length === 0) return;
		this._mount();
		this._observe();
		this._observeHero();
		this._recomputeDocMax();
		this._updateProgress();
		window.addEventListener("scroll", this._onScroll, { passive: true });
		window.addEventListener("resize", this._onResize, { passive: true });
		document.addEventListener("click", this._onDocClick, true);
		document.addEventListener("keydown", this._onKey);
	}

	// ─── Tree building ───────────────────────────────────────────────────

	private _build(): void {
		const levels = (this.getAttribute("levels") || "2,3")
			.split(",")
			.map((s) => Number.parseInt(s.trim(), 10))
			.filter((n) => n >= 1 && n <= 6)
			.sort((a, b) => a - b);
		if (levels.length === 0) return;

		const root = this.closest("rd-page") || document.body;
		const sel = levels.map((l) => `h${l}`).join(",");
		const headings = Array.from(root.querySelectorAll<HTMLElement>(sel)).filter(
			(h) => !this.contains(h),
		);
		if (headings.length === 0) return;

		// Compute the bar-height offset once so smooth-scroll lands the
		// heading just below the sticky bar in narrow mode. CSS sets
		// --_rd-toc-bar-h on the host; if it's missing fall back to 48px.
		const cs = getComputedStyle(this);
		const barH = Number.parseInt(cs.getPropertyValue("--_rd-toc-bar-h") || "48", 10) || 48;

		for (const h of headings) {
			if (!h.id) {
				h.id = slugify(h.textContent || "") || `h-${Math.random().toString(36).slice(2, 7)}`;
			}
			// Account for the sticky bar on smooth-scroll in narrow mode.
			// At ≥ 1024px the bar is hidden so the extra margin is invisible.
			h.style.scrollMarginTop = `${barH + 16}px`;
			this._entries.push({
				id: h.id,
				heading: h,
				anchor: null as unknown as HTMLAnchorElement, // filled at _mount
				level: Number.parseInt(h.tagName.slice(1), 10),
			});
		}
	}

	// ─── Rendering ───────────────────────────────────────────────────────

	private _mount(): void {
		const title = this.getAttribute("title") || "On this page";

		this.innerHTML = "";
		this.dataset.rdTocOpen = "false";
		this.dataset.rdTocVisible = "false";

		// Build two parallel trees (rail + popover) so each anchor lives in
		// its own DOM subtree but indexes the same heading. We track all
		// anchors per entry so active-state updates touch both.
		const railList = this._buildTree("rail");
		const popList = this._buildTree("pop");

		// Wide-mode rail.
		const rail = el(
			"nav",
			{ class: "_rd-toc-rail", "aria-label": title },
			el("div", { class: "_rd-toc-rail-title" }, title),
			el("div", { class: "_rd-toc-rail-list" }, railList),
		);

		// Narrow-mode bar + popover.
		const barCurrent = el("span", { class: "_rd-toc-bar-current" });
		const chev = el("span", { class: "_rd-toc-bar-chev", html: CHEVRON_DOWN_SVG });
		const button = el(
			"button",
			{
				class: "_rd-toc-bar-button",
				type: "button",
				"aria-expanded": "false",
				"aria-controls": "_rd-toc-pop",
				onClick: () => this._setOpen(this.dataset.rdTocOpen !== "true"),
			},
			el("span", { class: "_rd-toc-bar-eyebrow" }, title),
			el("span", { class: "_rd-toc-bar-sep", "aria-hidden": "true" }, "·"),
			barCurrent,
			chev,
		);
		const bar = el(
			"div",
			{ class: "_rd-toc-bar", role: "navigation", "aria-label": title },
			button,
		);

		const pop = el(
			"div",
			{
				class: "_rd-toc-pop",
				id: "_rd-toc-pop",
				role: "region",
				"aria-label": title,
			},
			el("div", { class: "_rd-toc-pop-inner" }, popList),
		);

		// Click delegation — close popover after navigation, run smooth
		// scroll honouring reduced-motion.
		const onAnchorClick = (ev: MouseEvent): void => {
			const a = (ev.target as HTMLElement | null)?.closest(
				"a[href^='#']",
			) as HTMLAnchorElement | null;
			if (!a) return;
			const id = decodeURIComponent(a.getAttribute("href")?.slice(1) || "");
			const target = id ? document.getElementById(id) : null;
			if (!target) return;
			ev.preventDefault();
			target.scrollIntoView({
				behavior: this._prefersReducedMotion ? "auto" : "smooth",
				block: "start",
			});
			// Tabbing should land on the heading after a click.
			if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
			target.focus({ preventScroll: true });
			history.replaceState(null, "", `#${id}`);
			this._setActive(id);
			this._setOpen(false);
		};
		rail.addEventListener("click", onAnchorClick);
		pop.addEventListener("click", onAnchorClick);

		this.appendChild(rail);
		this.appendChild(bar);
		this.appendChild(pop);

		this._rail = rail;
		this._railList = railList;
		this._bar = bar;
		this._barCurrent = barCurrent;
		this._pop = pop;
		this._popList = popList;
	}

	/** Build one <ul> tree of anchors for a presentation (rail | pop).
	 *  Side effect: fills `entry.anchor` on the first call only; on the
	 *  second call we extend each entry with the secondary anchor in a
	 *  parallel array stored on the entry (see _setActive). */
	private _buildTree(kind: "rail" | "pop"): HTMLElement {
		const levels = Array.from(new Set(this._entries.map((e) => e.level))).sort((a, b) => a - b);
		const depthOf = (lvl: number) => levels.indexOf(lvl);

		const rootUl = el("ul");
		const ulAtDepth: (HTMLElement | undefined)[] = [rootUl];

		for (const entry of this._entries) {
			const depth = depthOf(entry.level);
			if (depth < 0) continue;

			const a = el(
				"a",
				{ href: `#${entry.id}`, "data-rd-toc-id": entry.id },
				el("span", { class: "_rd-toc-text" }, entry.heading.textContent || ""),
			) as HTMLAnchorElement;

			if (kind === "rail") {
				entry.anchor = a;
			} else {
				// Stash the popover anchor as a sibling pointer so
				// _setActive can update both at once.
				(entry as unknown as { popAnchor: HTMLAnchorElement }).popAnchor = a;
			}

			const li = el("li", {}, a);

			if (depth === 0) {
				rootUl.appendChild(li);
				ulAtDepth[0] = rootUl;
				ulAtDepth.length = 1;
				continue;
			}

			let parentDepth = depth - 1;
			while (parentDepth >= 0 && !ulAtDepth[parentDepth]) parentDepth--;
			const parentUl = parentDepth >= 0 ? ulAtDepth[parentDepth] : rootUl;
			if (!parentUl) {
				rootUl.appendChild(li);
				continue;
			}
			const parentLi = parentUl.lastElementChild as HTMLElement | null;
			if (!parentLi) {
				parentUl.appendChild(li);
				continue;
			}
			let nested = parentLi.querySelector<HTMLElement>(":scope > ul");
			if (!nested) {
				nested = el("ul");
				parentLi.appendChild(nested);
			}
			nested.appendChild(li);
			ulAtDepth[depth] = nested;
			ulAtDepth.length = depth + 1;
		}

		return rootUl;
	}

	// ─── Active-section tracking ─────────────────────────────────────────

	private _observe(): void {
		// rootMargin biases active selection toward the upper third of the
		// viewport — a heading "becomes active" as it crosses into the top
		// quarter, and stays active until the next one takes over.
		this._headingIo = new IntersectionObserver(
			(records) => {
				// We may receive multiple intersection updates per frame.
				// Pick the most recent "above the fold" heading by document
				// order rather than trusting one record.
				for (const r of records) {
					(r.target as HTMLElement).dataset.rdTocIntersecting = r.isIntersecting ? "1" : "0";
				}
				this._recomputeActive();
			},
			{
				rootMargin: "-20% 0px -70% 0px",
				threshold: 0,
			},
		);
		for (const e of this._entries) this._headingIo.observe(e.heading);
		// Seed an initial active entry based on current scroll position so
		// the rail doesn't open empty.
		this._recomputeActive();
	}

	private _recomputeActive(): void {
		// Among entries marked intersecting, pick the last one in document
		// order. If none are intersecting (between sections), keep the
		// last heading we passed (compare offsetTop to scrollY).
		let active: TocEntry | null = null;
		for (const e of this._entries) {
			if (e.heading.dataset.rdTocIntersecting === "1") active = e;
		}
		if (!active) {
			const y = window.scrollY + window.innerHeight * 0.2;
			for (const e of this._entries) {
				if (e.heading.getBoundingClientRect().top + window.scrollY <= y) {
					active = e;
				}
			}
		}
		this._setActive(active?.id ?? null);
	}

	private _setActive(id: string | null): void {
		if (id === this._activeId) return;
		this._activeId = id;
		for (const e of this._entries) {
			const popAnchor = (e as unknown as { popAnchor?: HTMLAnchorElement }).popAnchor;
			if (e.id === id) {
				e.anchor.setAttribute("aria-current", "true");
				popAnchor?.setAttribute("aria-current", "true");
			} else {
				e.anchor.removeAttribute("aria-current");
				popAnchor?.removeAttribute("aria-current");
			}
		}
		if (this._barCurrent) {
			const active = id ? this._entries.find((e) => e.id === id) : null;
			this._barCurrent.textContent = active ? active.heading.textContent?.trim() || "" : "";
		}
		// Keep the rail list scrolled so the active entry stays visible.
		if (this._railList && id) {
			const a = this._railList.querySelector<HTMLAnchorElement>(
				`a[data-rd-toc-id="${CSS.escape(id)}"]`,
			);
			if (a) {
				const listRect = this._railList.getBoundingClientRect();
				const aRect = a.getBoundingClientRect();
				if (aRect.top < listRect.top + 8 || aRect.bottom > listRect.bottom - 8) {
					a.scrollIntoView({ block: "nearest" });
				}
			}
		}
	}

	// ─── Hero sentinel (narrow-mode bar visibility) ──────────────────────

	private _observeHero(): void {
		const page = this.closest("rd-page");
		const sentinel =
			page?.querySelector<HTMLElement>("rd-hero") ??
			(page?.firstElementChild as HTMLElement | null);
		if (!sentinel) {
			this.dataset.rdTocVisible = "true";
			return;
		}
		this._heroIo = new IntersectionObserver(
			([entry]) => {
				this.dataset.rdTocVisible = entry.isIntersecting ? "false" : "true";
				if (entry.isIntersecting) this._setOpen(false);
			},
			{ threshold: 0 },
		);
		this._heroIo.observe(sentinel);
	}

	// ─── Progress fill ───────────────────────────────────────────────────

	private _recomputeDocMax(): void {
		const doc = document.documentElement;
		this._docMaxScroll = Math.max(0, (doc.scrollHeight || 0) - window.innerHeight);
	}

	private _scheduleProgressUpdate(): void {
		if (this._rafPending) return;
		this._rafPending = true;
		requestAnimationFrame(() => {
			this._rafPending = false;
			this._updateProgress();
		});
	}

	private _updateProgress(): void {
		const p =
			this._docMaxScroll > 0 ? Math.min(1, Math.max(0, window.scrollY / this._docMaxScroll)) : 0;
		this.style.setProperty("--rd-toc-progress", p.toFixed(4));
	}

	// ─── Narrow-mode popover state ───────────────────────────────────────

	private _setOpen(open: boolean): void {
		const next = open ? "true" : "false";
		if (this.dataset.rdTocOpen === next) return;
		this.dataset.rdTocOpen = next;
		const button = this._bar?.querySelector<HTMLElement>("._rd-toc-bar-button");
		button?.setAttribute("aria-expanded", next);
	}
}

export function register(): void {
	define(tagName, RdToc);
}
export { spec, tagName };
