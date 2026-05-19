import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { slugify } from "../../lib/text.ts";
import { chapterSpec, chapterTagName, spec, tagName } from "./toc.schema.ts";

/* rd-toc — floating, sticky table of contents.
 *
 * Two modes, auto-detected at upgrade time:
 *
 *   headings (default)
 *     Walks <rd-page> headings and renders a single-file TOC. This is the
 *     original behaviour.
 *
 *   book
 *     Triggered when the host element has any <rd-chapter> descendant.
 *     Renders a cross-file chapter tree; the active chapter is auto-
 *     detected by matching `location.pathname` against each chapter's
 *     `href`. In-page headings are still discovered and merged inline as
 *     a sub-tree under the active chapter (Sphinx-style). Prev / next
 *     bands are auto-injected at the top and bottom of <rd-page>.
 *
 * Lifecycle:
 *   1. _detectMode()  Peek for <rd-chapter> to decide the branch.
 *   2. _buildBook()   (book mode) Parse the chapter tree from light DOM.
 *   3. _build()       Walk <rd-page> headings (always — headings mode
 *                     uses them for the whole TOC, book mode uses them
 *                     for the active-chapter expansion).
 *   4. _mount()       Render the shared rail/bar/popover chrome, with
 *                     the inner list built by either the headings or
 *                     book tree builder.
 *   5. _observe()     IntersectionObserver tracks the active heading.
 *   6. _injectPageNav() (book mode) Insert prev/next bands.
 *   7. _observeHero() Narrow-mode bar visibility.
 *   8. scroll + rAF   Update --rd-toc-progress.
 *
 * The host element is `display: contents`; the rail, bar and popover are
 * the painted children. The page.css :has(rd-toc) grid rule flips the
 * host to `display: block` at the breakpoint so the rail has a sticking
 * context.
 */

interface TocEntry {
	id: string;
	heading: HTMLElement;
	anchor: HTMLAnchorElement;
	level: number;
}

interface BookEntry {
	href: string | null; // null = group header
	title: string;
	url: URL | null; // resolved against location.href; null if no href / invalid
	level: number; // nesting depth, 0-based
	children: BookEntry[];
	parent: BookEntry | null;
	isActive: boolean;
}

/** Chevron-down icon, drawn inline so we don't pull in <rd-icon>'s CDN
 *  fetch for a single static glyph that's always visible. */
const CHEVRON_DOWN_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
	stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
	aria-hidden="true" focusable="false"><path d="M6 9l6 6 6-6"/></svg>`;

/** Treat a trailing slash like /index.html so chapter hrefs match the
 *  current page regardless of how the server canonicalises the path. */
function _normalizePath(u: URL): string {
	const p = u.pathname.endsWith("/") ? `${u.pathname}index.html` : u.pathname;
	return `${u.origin}${p}`;
}

class RdToc extends HTMLElement implements Upgradeable {
	_upgraded = false;

	private _mode: "headings" | "book" = "headings";
	private _entries: TocEntry[] = [];
	private _activeId: string | null = null;
	private _book: BookEntry[] = [];
	private _bookFlat: BookEntry[] = [];
	private _activeBookEntry: BookEntry | null = null;
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
		this._detectMode();
		if (this._mode === "book") {
			this._buildBook();
			// If chapter parsing produced nothing usable, fall back to
			// headings mode so the page still gets a TOC.
			if (this._book.length === 0) this._mode = "headings";
		}

		// In both modes we want the in-page heading list: headings mode
		// uses it as the whole TOC, book mode splices it under the active
		// chapter.
		this._build();

		const haveBook = this._mode === "book" && this._book.length > 0;
		const haveHeadings = this._entries.length > 0;
		if (!haveBook && !haveHeadings) return;

		this._mount();
		if (haveHeadings) this._observe();
		if (haveBook) this._injectPageNav();
		this._observeHero();
		this._recomputeDocMax();
		this._updateProgress();
		this._wireListeners();
	}

	private _detectMode(): void {
		this._mode = this.querySelector("rd-chapter") ? "book" : "headings";
	}

	private _wireListeners(): void {
		window.addEventListener("scroll", this._onScroll, { passive: true });
		window.addEventListener("resize", this._onResize, { passive: true });
		document.addEventListener("click", this._onDocClick, true);
		document.addEventListener("keydown", this._onKey);
	}

	// ─── Book parsing ────────────────────────────────────────────────────

	private _buildBook(): void {
		const hereKey = _normalizePath(new URL(location.href));

		const walk = (root: Element, depth: number, parent: BookEntry | null): BookEntry[] => {
			const out: BookEntry[] = [];
			for (const node of Array.from(root.children)) {
				if (node.tagName.toLowerCase() !== "rd-chapter") continue;
				const ch = node as HTMLElement;
				const href = ch.getAttribute("href");
				const title = this._chapterTitle(ch);
				let url: URL | null = null;
				let active = false;
				if (href) {
					try {
						url = new URL(href, location.href);
						active = _normalizePath(url) === hereKey;
					} catch {
						url = null;
					}
				}
				const entry: BookEntry = {
					href,
					title,
					url,
					level: depth,
					children: [],
					parent,
					isActive: active,
				};
				entry.children = walk(ch, depth + 1, entry);
				out.push(entry);
			}
			return out;
		};

		this._book = walk(this, 0, null);
		this._bookFlat = [];
		const flatten = (xs: BookEntry[]): void => {
			for (const x of xs) {
				this._bookFlat.push(x);
				if (x.children.length) flatten(x.children);
			}
		};
		flatten(this._book);
		this._activeBookEntry = this._bookFlat.find((e) => e.isActive) || null;
	}

	private _chapterTitle(ch: HTMLElement): string {
		// Title is the chapter element's text content excluding any nested
		// <rd-chapter> sub-trees.
		const clone = ch.cloneNode(true) as HTMLElement;
		for (const nested of Array.from(clone.querySelectorAll("rd-chapter"))) {
			nested.remove();
		}
		return (clone.textContent || "").replace(/\s+/g, " ").trim();
	}

	// ─── Heading tree building ───────────────────────────────────────────

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
		const title =
			this.getAttribute("title") || (this._mode === "book" ? "Contents" : "On this page");

		this.innerHTML = "";
		this.dataset.rdTocOpen = "false";
		this.dataset.rdTocVisible = "false";

		const railList =
			this._mode === "book" ? this._buildBookList("rail") : this._buildHeadingsList("rail");
		const popList =
			this._mode === "book" ? this._buildBookList("pop") : this._buildHeadingsList("pop");

		// Wide-mode rail.
		const rail = el(
			"nav",
			{ class: "_rd-toc-rail", "aria-label": title },
			el("div", { class: "_rd-toc-rail-title" }, title),
			el("div", { class: "_rd-toc-rail-list" }, railList),
		);

		// Narrow-mode bar + popover.
		const barCurrent = el("span", { class: "_rd-toc-bar-current" });
		// In book mode the bar's current label tracks the chapter (set
		// once); the heading observer would otherwise overwrite it on
		// scroll. Headings mode populates it from _setActive().
		if (this._mode === "book" && this._activeBookEntry) {
			barCurrent.textContent = this._activeBookEntry.title;
		}
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
		// scroll honouring reduced-motion. Cross-file chapter links (which
		// do not start with '#') are left alone and navigate normally.
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

	/** Build the rail/pop list in headings mode. */
	private _buildHeadingsList(kind: "rail" | "pop"): HTMLElement {
		return this._buildHeadingsTree(kind, this._entries);
	}

	/** Build the rail/pop list in book mode: chapter tree with the active
	 *  chapter expanded to show in-page headings. */
	private _buildBookList(kind: "rail" | "pop"): HTMLElement {
		const rootUl = el("ul");
		const renderEntry = (entry: BookEntry, into: HTMLElement): void => {
			const titleNode = el("span", { class: "_rd-toc-text" }, entry.title);
			const label = entry.href
				? (el(
						"a",
						{
							href: entry.href,
							"data-rd-chapter-href": entry.href,
							...(entry.isActive ? { "aria-current": "page" } : {}),
						},
						titleNode,
					) as HTMLElement)
				: (el("span", { class: "_rd-toc-group" }, titleNode) as HTMLElement);
			const li = el("li", {}, label) as HTMLElement;

			// Splice in-page headings under the active chapter.
			if (entry.isActive && this._entries.length > 0) {
				li.appendChild(this._buildHeadingsTree(kind, this._entries));
			}

			if (entry.children.length > 0) {
				const sub = el("ul");
				for (const c of entry.children) renderEntry(c, sub);
				li.appendChild(sub);
			}
			into.appendChild(li);
		};
		for (const e of this._book) renderEntry(e, rootUl);
		return rootUl;
	}

	/** Build one <ul> tree of anchors for a presentation (rail | pop)
	 *  from the heading entries.
	 *
	 *  Side effect: fills `entry.anchor` on the rail call and stashes a
	 *  `.popAnchor` on the entry on the pop call, so `_setActive` can
	 *  update both anchors at once.
	 */
	private _buildHeadingsTree(kind: "rail" | "pop", entries: TocEntry[]): HTMLElement {
		const levels = Array.from(new Set(entries.map((e) => e.level))).sort((a, b) => a - b);
		const depthOf = (lvl: number) => levels.indexOf(lvl);

		const rootUl = el("ul");
		const ulAtDepth: (HTMLElement | undefined)[] = [rootUl];

		for (const entry of entries) {
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

	// ─── Prev/next page navigation (book mode) ───────────────────────────

	private _injectPageNav(): void {
		if (!this._activeBookEntry) return;
		// Only navigable chapters (with an href) participate in prev/next.
		// Group headers are skipped; external URLs are kept so reading
		// order in the source reflects intent.
		const flat = this._bookFlat.filter((e) => !!e.href);
		const idx = flat.indexOf(this._activeBookEntry);
		if (idx < 0) return;
		const prev = idx > 0 ? flat[idx - 1] : null;
		const next = idx < flat.length - 1 ? flat[idx + 1] : null;
		if (!prev && !next) return;

		const page = this.closest("rd-page");
		if (!page) return;

		const make = (pos: "top" | "bottom"): HTMLElement => {
			const nav = el("nav", {
				class: "_rd-pagenav",
				"data-rd-pagenav": pos,
				"aria-label": pos === "top" ? "Top page navigation" : "Bottom page navigation",
			}) as HTMLElement;
			nav.appendChild(this._pagenavSide("prev", prev));
			nav.appendChild(this._pagenavSide("next", next));
			return nav;
		};

		// Top band: after <rd-banner> if present, otherwise the first
		// child of <rd-page>.
		const banner = page.querySelector(":scope > rd-banner");
		const top = make("top");
		if (banner) banner.after(top);
		else page.prepend(top);

		// Bottom band: append at the end of <rd-page>. Later upgrades
		// (footnotes, references) append after us — reading order ends
		// up: …content → pagenav → footnotes → references, which is what
		// we want.
		page.appendChild(make("bottom"));
	}

	private _pagenavSide(kind: "prev" | "next", entry: BookEntry | null): HTMLElement {
		if (!entry || !entry.href) {
			return el("span", {
				class: `_rd-pagenav-side _rd-pagenav-${kind} _rd-pagenav-empty`,
				"aria-hidden": "true",
			}) as HTMLElement;
		}
		return el(
			"a",
			{
				class: `_rd-pagenav-side _rd-pagenav-${kind}`,
				href: entry.href,
				rel: kind === "prev" ? "prev" : "next",
			},
			el("span", { class: "_rd-pagenav-eyebrow" }, kind === "prev" ? "Previous" : "Next"),
			el("span", { class: "_rd-pagenav-title" }, entry.title),
		) as HTMLElement;
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
				e.anchor?.setAttribute("aria-current", "true");
				popAnchor?.setAttribute("aria-current", "true");
			} else {
				e.anchor?.removeAttribute("aria-current");
				popAnchor?.removeAttribute("aria-current");
			}
		}
		// In book mode the bar's "current" label is pinned to the chapter
		// title (set at mount time). In headings mode we track the heading.
		if (this._mode !== "book" && this._barCurrent) {
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
export { chapterSpec, chapterTagName, spec, tagName };
