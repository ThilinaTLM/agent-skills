import { loadCdnStyle } from "../../lib/cdn.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, shotSpec, shotTagName, tagName } from "./gallery.schema.ts";

const PHOTOSWIPE_CSS_URL = "https://cdn.jsdelivr.net/npm/photoswipe@5/dist/photoswipe.css";
const PHOTOSWIPE_LIGHTBOX_URL =
	"https://cdn.jsdelivr.net/npm/photoswipe@5/dist/photoswipe-lightbox.esm.min.js";

interface ShotMeta {
	src: string;
	alt: string;
	caption: string | null;
	width: number;
	height: number;
}

interface PhotoSwipeLightboxModule {
	default: new (opts: Record<string, unknown>) => { init: () => void };
}

let lightboxModule: Promise<PhotoSwipeLightboxModule | null> | null = null;

async function loadPhotoSwipeLightbox(): Promise<PhotoSwipeLightboxModule | null> {
	if (lightboxModule) return lightboxModule;
	loadCdnStyle(PHOTOSWIPE_CSS_URL);
	lightboxModule = import(/* @vite-ignore */ PHOTOSWIPE_LIGHTBOX_URL).catch((err) => {
		console.warn("[richdoc] PhotoSwipe load failed:", err);
		return null;
	});
	return lightboxModule;
}

/**
 * <rd-gallery> — grid of <rd-shot> images. Click a shot to open a
 * PhotoSwipe lightbox; with no JS / no network, the grid links still
 * open the full image in a new tab.
 */
class RdGallery extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const cols = this.getAttribute("cols") || "3";
		const title = this.getAttribute("title");
		this.setAttribute("data-cols", cols);

		const shots = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-shot"));
		const metas = await Promise.all(shots.map(async (s) => parseShot(s)));

		this.innerHTML = "";
		if (title) this.appendChild(el("div", { class: "_rd-gallery-title" }, title));
		const grid = el("div", { class: "_rd-gallery-grid", id: `_rd-gallery-${Date.now()}` });
		grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
		this.appendChild(grid);

		for (const meta of metas) {
			const a = el(
				"a",
				{
					class: "_rd-gallery-item",
					href: meta.src,
					target: "_blank",
					rel: "noopener",
					"data-pswp-width": String(meta.width),
					"data-pswp-height": String(meta.height),
				},
				el("img", {
					src: meta.src,
					alt: meta.alt,
					loading: "lazy",
				}),
			);
			if (meta.caption) {
				a.appendChild(el("span", { class: "_rd-gallery-caption" }, meta.caption));
			}
			grid.appendChild(a);
		}

		// Wire up PhotoSwipe lazily.
		const mod = await loadPhotoSwipeLightbox();
		if (!mod || !grid.id) return;
		try {
			const Lightbox = mod.default;
			const lb = new Lightbox({
				gallery: `#${grid.id}`,
				children: "a._rd-gallery-item",
				pswpModule: () =>
					import(/* @vite-ignore */ "https://cdn.jsdelivr.net/npm/photoswipe@5/dist/photoswipe.esm.min.js"),
			});
			lb.init();
		} catch (err) {
			console.warn("[richdoc] PhotoSwipe init failed:", err);
		}
	}
}

function parseShot(shot: HTMLElement): Promise<ShotMeta> {
	const src = shot.getAttribute("src") || "";
	const alt = shot.getAttribute("alt") || "";
	const caption = shot.getAttribute("caption");
	const wAttr = shot.getAttribute("width");
	const hAttr = shot.getAttribute("height");
	if (wAttr && hAttr) {
		return Promise.resolve({
			src,
			alt,
			caption,
			width: Number(wAttr) || 1600,
			height: Number(hAttr) || 1000,
		});
	}
	return new Promise((resolve) => {
		const img = new Image();
		img.onload = () =>
			resolve({
				src,
				alt,
				caption,
				width: img.naturalWidth || 1600,
				height: img.naturalHeight || 1000,
			});
		img.onerror = () => resolve({ src, alt, caption, width: 1600, height: 1000 });
		img.src = src;
	});
}

class RdShot extends HTMLElement {
	// Pure declaration; the gallery reads its attributes during upgrade.
}

export function register(): void {
	define(tagName, RdGallery);
	define(shotTagName, RdShot);
}

export { spec, tagName, shotSpec, shotTagName };
