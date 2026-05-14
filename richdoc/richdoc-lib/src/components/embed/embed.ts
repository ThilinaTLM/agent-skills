import { loadCdnScript, loadCdnStyle } from "../../lib/cdn.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./embed.schema.ts";

/**
 * <rd-embed> — generic embed wrapper. Detects YouTube / Vimeo URLs and
 * uses the matching lite-element web component for fast initial paint.
 * Anything else renders as a plain sandboxed <iframe>.
 *
 * Offline / load failure: shows a plain link to the source.
 */

const LITE_YOUTUBE_JS_URL =
	"https://cdn.jsdelivr.net/npm/lite-youtube-embed@0.3.3/src/lite-yt-embed.js";
const LITE_YOUTUBE_CSS_URL =
	"https://cdn.jsdelivr.net/npm/lite-youtube-embed@0.3.3/src/lite-yt-embed.css";
const LITE_VIMEO_JS_URL =
	"https://cdn.jsdelivr.net/npm/@slightlyoff/lite-vimeo@0.1.2/lite-vimeo.js";

interface ParsedSrc {
	kind: "youtube" | "vimeo" | "iframe";
	id?: string;
	url: string;
}

function parseSrc(src: string): ParsedSrc {
	try {
		const u = new URL(src);
		if (/(^|\.)youtube\.com$/.test(u.hostname)) {
			const v = u.searchParams.get("v");
			if (v) return { kind: "youtube", id: v, url: src };
			const short = u.pathname.match(/^\/embed\/([^/?]+)/);
			if (short) return { kind: "youtube", id: short[1], url: src };
		}
		if (u.hostname === "youtu.be") {
			const id = u.pathname.slice(1).split(/[/?]/)[0];
			if (id) return { kind: "youtube", id, url: src };
		}
		if (/(^|\.)vimeo\.com$/.test(u.hostname)) {
			const id = u.pathname.split("/").filter(Boolean).pop();
			if (id && /^\d+$/.test(id)) return { kind: "vimeo", id, url: src };
		}
	} catch {
		/* fall through */
	}
	return { kind: "iframe", url: src };
}

class RdEmbed extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const src = this.getAttribute("src") || "";
		const title = this.getAttribute("title") || "Embed";
		const aspect = this.getAttribute("aspect") || "16:9";
		const caption = this.getAttribute("caption");

		this.innerHTML = "";
		const frame = el("div", { class: "_rd-embed-frame" });
		frame.style.aspectRatio = aspect.replace(":", " / ");
		this.appendChild(frame);
		if (caption) this.appendChild(el("div", { class: "_rd-embed-caption" }, caption));

		const parsed = parseSrc(src);
		try {
			if (parsed.kind === "youtube" && parsed.id) {
				loadCdnStyle(LITE_YOUTUBE_CSS_URL);
				await loadCdnScript<unknown>(
					LITE_YOUTUBE_JS_URL,
					() => (window.customElements?.get("lite-youtube") ? true : undefined),
				);
				const lyt = document.createElement("lite-youtube");
				lyt.setAttribute("videoid", parsed.id);
				lyt.setAttribute("playlabel", title);
				frame.appendChild(lyt);
			} else if (parsed.kind === "vimeo" && parsed.id) {
				await loadCdnScript<unknown>(
					LITE_VIMEO_JS_URL,
					() => (window.customElements?.get("lite-vimeo") ? true : undefined),
				);
				const lv = document.createElement("lite-vimeo");
				lv.setAttribute("videoid", parsed.id);
				frame.appendChild(lv);
			} else {
				const iframe = document.createElement("iframe");
				iframe.src = src;
				iframe.title = title;
				iframe.loading = "lazy";
				iframe.referrerPolicy = "no-referrer-when-downgrade";
				iframe.setAttribute("allowfullscreen", "");
				iframe.setAttribute(
					"sandbox",
					"allow-scripts allow-same-origin allow-popups allow-forms",
				);
				frame.appendChild(iframe);
			}
		} catch (err) {
			console.warn("[richdoc] embed failed:", err);
			frame.innerHTML = "";
			frame.appendChild(
				el(
					"a",
					{ class: "_rd-embed-fallback", href: src, target: "_blank", rel: "noopener" },
					`Open ${title}`,
				),
			);
		}
	}
}

export function register(): void {
	define(tagName, RdEmbed);
}
export { spec, tagName };
