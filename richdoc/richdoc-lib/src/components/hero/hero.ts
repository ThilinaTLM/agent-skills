import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./hero.schema.ts";

/**
 * <rd-hero> — magazine-style top-of-page header.
 *
 * Attributes:
 *   - eyebrow?  Small caps kicker above the title.
 *   - title     The main title; renders at display opsz 144.
 *   - lede?     One-sentence intro in Fraunces italic.
 *   - meta?     Quiet meta line (e.g. "Updated Jan 2026 · Platform team").
 *
 * Any inline children remain after the meta line — useful for an
 * <rd-kv> or <rd-badge> strip directly under the hero.
 *
 * Book mode: when the document contains an <rd-toc> with at least one
 * <rd-chapter href> child, the auto-injected prev/next bands cover
 * chapter navigation. Any <a> children of the hero whose href resolves
 * to another book chapter (or whose text matches the legacy
 * prev/next/up/index pattern) are silently dropped so the page does
 * not double-render navigation. The meta attribute is also scrubbed of
 * "Prev:/Next:/Up:" segments. These guards are belt-and-braces — the
 * lint rule `hero-nav-redundant` catches the same patterns at authoring
 * time.
 */

// Legacy nav-anchor text: arrow glyphs + the english nav words.
const HERO_NAV_TEXT_RE = /^\s*(?:[\u2190\u2191\u2192\u2193]|prev(?:ious)?|next|up|home|index)\b/i;

// "Prev:/Next:/Up:" segments inside the meta attribute.
const HERO_META_NAV_SEG_RE = /^\s*(prev(?:ious)?|next|up)\s*:/i;

// richdoc convention for joining hero meta segments.
const HERO_META_SEPARATOR = " \u00b7 ";

interface BookSignals {
	readonly isBook: boolean;
	readonly chapterUrls: ReadonlySet<string>;
}

function detectBookSignals(doc: Document): BookSignals {
	const cached = (doc as unknown as { _rdHeroBookSignals?: BookSignals })._rdHeroBookSignals;
	if (cached) return cached;
	const chapterUrls = new Set<string>();
	let isBook = false;
	for (const toc of Array.from(doc.querySelectorAll("rd-toc"))) {
		for (const ch of Array.from(toc.querySelectorAll("rd-chapter"))) {
			const href = ch.getAttribute("href");
			if (!href) continue;
			try {
				const url = new URL(href, doc.location?.href || "http://localhost/");
				chapterUrls.add(url.href);
				isBook = true;
			} catch {
				// Skip unparseable hrefs — they cannot match anyway.
			}
		}
	}
	const signals: BookSignals = { isBook, chapterUrls };
	(doc as unknown as { _rdHeroBookSignals?: BookSignals })._rdHeroBookSignals = signals;
	return signals;
}

function isLegacyNavAnchor(node: Node, signals: BookSignals): boolean {
	if (!(node instanceof HTMLAnchorElement)) return false;
	const href = (node.getAttribute("href") || "").trim();
	const text = (node.textContent || "").trim();
	if (href) {
		try {
			const url = new URL(href, node.ownerDocument?.location?.href || "http://localhost/");
			if (signals.chapterUrls.has(url.href)) return true;
		} catch {
			// fall through
		}
	}
	if (text && HERO_NAV_TEXT_RE.test(text)) return true;
	return false;
}

function scrubHeroMeta(meta: string): string {
	if (!meta) return meta;
	const segments = meta.split(HERO_META_SEPARATOR.trim()).map((s) => s.trim());
	const kept = segments.filter((s) => s && !HERO_META_NAV_SEG_RE.test(s));
	return kept.join(HERO_META_SEPARATOR).trim();
}

class RdHero extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const eyebrow = this.getAttribute("eyebrow");
		const title = this.getAttribute("title") || "";
		const lede = this.getAttribute("lede");
		let meta = this.getAttribute("meta");

		const signals = detectBookSignals(this.ownerDocument || document);
		if (signals.isBook && meta) {
			const scrubbed = scrubHeroMeta(meta);
			meta = scrubbed || null;
		}

		// Capture any pre-existing children (e.g. an <rd-kv>) before we
		// rebuild the host's internals. In book mode, legacy nav anchors
		// are dropped.
		const rawExtras = Array.from(this.childNodes);
		const extras = signals.isBook
			? rawExtras.filter((n) => !isLegacyNavAnchor(n, signals))
			: rawExtras;
		this.innerHTML = "";

		if (eyebrow) this.appendChild(el("div", { class: "_rd-hero-eyebrow" }, eyebrow));
		this.appendChild(el("h1", { class: "_rd-hero-title" }, title));
		if (lede) this.appendChild(el("p", { class: "_rd-hero-lede" }, lede));
		if (meta) this.appendChild(el("div", { class: "_rd-hero-meta" }, meta));
		if (extras.length) {
			const extrasWrap = el("div", { class: "_rd-hero-extras" });
			for (const node of extras) extrasWrap.appendChild(node);
			this.appendChild(extrasWrap);
		}
	}
}

export function register(): void {
	define(tagName, RdHero);
}
export { spec, tagName };
