/**
 * Preview-picker preference store.
 *
 * The floating `<rd-prefs>` toolbar writes its three knobs (theme, mode,
 * width) here so a reader's selection survives reload. Stored per
 * `origin + pathname` so book chapters in distinct files get independent
 * preferences without leaking across hosts.
 *
 * The store is intentionally tiny and synchronous — it's read once at
 * `<rd-page>` upgrade time to override the author's initial attributes
 * before the entry cascade flips the page visible, and written on every
 * picker change. `localStorage` access is wrapped so private-mode or
 * disabled-storage browsers never throw.
 */

export type Theme = "editorial-warm" | "graphite-modern";
export type Mode = "light" | "dark" | "auto";
export type Width = "narrow" | "standard" | "wide" | "full";
export type TocPos = "auto" | "right" | "left" | "top";

export interface Prefs {
	theme?: Theme;
	mode?: Mode;
	width?: Width;
	toc?: TocPos;
}

const KEY_PREFIX = "rd-prefs:";

const VALID_THEME: ReadonlyArray<Theme> = ["editorial-warm", "graphite-modern"];
const VALID_MODE: ReadonlyArray<Mode> = ["light", "dark", "auto"];
const VALID_WIDTH: ReadonlyArray<Width> = ["narrow", "standard", "wide", "full"];
const VALID_TOC_POS: ReadonlyArray<TocPos> = ["auto", "right", "left", "top"];

function storageKey(): string {
	// `file://` docs land here with an empty origin (or `null`) plus a
	// pathname; that's fine — every distinct file still gets its own
	// bucket via the pathname half.
	const loc = globalThis.location;
	const origin = loc?.origin || "";
	const path = loc?.pathname || "";
	return `${KEY_PREFIX}${origin}${path}`;
}

function safeStorage(): Storage | null {
	try {
		const ls = globalThis.localStorage;
		// Probe write — private-mode Safari throws on setItem despite
		// exposing localStorage.
		const probe = `${KEY_PREFIX}__probe`;
		ls.setItem(probe, "1");
		ls.removeItem(probe);
		return ls;
	} catch {
		return null;
	}
}

/** Read the current document's stored prefs, or an empty object. */
export function loadPrefs(): Prefs {
	const ls = safeStorage();
	if (!ls) return {};
	let raw: string | null;
	try {
		raw = ls.getItem(storageKey());
	} catch {
		return {};
	}
	if (!raw) return {};
	let parsed: unknown;
	try {
		parsed = JSON.parse(raw);
	} catch {
		return {};
	}
	if (!parsed || typeof parsed !== "object") return {};
	const out: Prefs = {};
	const p = parsed as Record<string, unknown>;
	if (typeof p.theme === "string" && (VALID_THEME as readonly string[]).includes(p.theme)) {
		out.theme = p.theme as Theme;
	}
	if (typeof p.mode === "string" && (VALID_MODE as readonly string[]).includes(p.mode)) {
		out.mode = p.mode as Mode;
	}
	if (typeof p.width === "string" && (VALID_WIDTH as readonly string[]).includes(p.width)) {
		out.width = p.width as Width;
	}
	if (typeof p.toc === "string" && (VALID_TOC_POS as readonly string[]).includes(p.toc)) {
		out.toc = p.toc as TocPos;
	}
	return out;
}

/** Merge-write the given prefs subset; leaves unrelated keys untouched. */
export function savePrefs(patch: Prefs): void {
	const ls = safeStorage();
	if (!ls) return;
	const current = loadPrefs();
	const merged: Prefs = { ...current, ...patch };
	// Drop empty entries to keep the bucket small.
	for (const k of Object.keys(merged) as (keyof Prefs)[]) {
		if (merged[k] == null) delete merged[k];
	}
	try {
		ls.setItem(storageKey(), JSON.stringify(merged));
	} catch {
		// best-effort: surface in console only when debugging
	}
}

/** Clear every stored knob for the current document. */
export function clearPrefs(): void {
	const ls = safeStorage();
	if (!ls) return;
	try {
		ls.removeItem(storageKey());
	} catch {
		// ignore
	}
}
