/**
 * Preview-picker preference store.
 *
 * The floating `<rd-prefs>` toolbar writes its four appearance knobs
 * (theme, mode, width, TOC position) here so a reader's selection
 * survives reload. Stored in a single bucket per origin (browser
 * localStorage is already origin-isolated), shared across every richdoc
 * document the reader opens on that origin — so picking "dark + wide"
 * on one file applies to the next file too. Author attributes on
 * `<rd-page>` still act as fallbacks when no pref is stored.
 *
 * The store is intentionally tiny and synchronous — it's read once at
 * `<rd-page>` upgrade time to override the author's initial attributes
 * before the entry cascade flips the page visible, and written on every
 * picker change. `localStorage` access is wrapped so private-mode or
 * disabled-storage browsers never throw.
 *
 * On first load after upgrading from the old per-file scheme, any
 * surviving `rd-prefs:<origin><path>` entries are folded into the new
 * global bucket and then deleted — see `migrateLegacy` below.
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

/** Single global key for the current origin. */
const STORAGE_KEY = "rd-prefs";
/** Prefix of the legacy per-file keys (`rd-prefs:<origin><path>`). */
const LEGACY_PREFIX = "rd-prefs:";
/** Probe key used to detect a writable localStorage. */
const PROBE_KEY = "rd-prefs:__probe";

const VALID_THEME: ReadonlyArray<Theme> = ["editorial-warm", "graphite-modern"];
const VALID_MODE: ReadonlyArray<Mode> = ["light", "dark", "auto"];
const VALID_WIDTH: ReadonlyArray<Width> = ["narrow", "standard", "wide", "full"];
const VALID_TOC_POS: ReadonlyArray<TocPos> = ["auto", "right", "left", "top"];

function safeStorage(): Storage | null {
	try {
		const ls = globalThis.localStorage;
		// Probe write — private-mode Safari throws on setItem despite
		// exposing localStorage.
		ls.setItem(PROBE_KEY, "1");
		ls.removeItem(PROBE_KEY);
		return ls;
	} catch {
		return null;
	}
}

/** Parse and validate a JSON-serialised Prefs blob. Unknown / invalid
 * fields are dropped silently. */
function parsePrefs(raw: string | null): Prefs {
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

/** One-time sweep of legacy per-file `rd-prefs:<origin><path>` keys.
 *
 * Called from `loadPrefs` only when the global bucket is empty so it
 * runs at most once per origin after the upgrade. All legacy entries
 * are folded together (last valid value wins per field) and written to
 * the new global key, then every legacy key is removed so the origin's
 * localStorage doesn't accumulate cruft. Returns the merged Prefs (or
 * an empty object if nothing usable was found). */
function migrateLegacy(ls: Storage): Prefs {
	let legacyKeys: string[];
	try {
		legacyKeys = [];
		for (let i = 0; i < ls.length; i++) {
			const k = ls.key(i);
			if (k && k !== STORAGE_KEY && k !== PROBE_KEY && k.startsWith(LEGACY_PREFIX)) {
				legacyKeys.push(k);
			}
		}
	} catch {
		return {};
	}
	if (legacyKeys.length === 0) return {};

	const merged: Prefs = {};
	for (const k of legacyKeys) {
		let raw: string | null = null;
		try {
			raw = ls.getItem(k);
		} catch {
			continue;
		}
		Object.assign(merged, parsePrefs(raw));
	}

	if (Object.keys(merged).length > 0) {
		try {
			ls.setItem(STORAGE_KEY, JSON.stringify(merged));
		} catch {
			// best-effort
		}
	}
	for (const k of legacyKeys) {
		try {
			ls.removeItem(k);
		} catch {
			// ignore
		}
	}
	return merged;
}

/** Read the stored prefs for this origin, or an empty object. */
export function loadPrefs(): Prefs {
	const ls = safeStorage();
	if (!ls) return {};
	let raw: string | null;
	try {
		raw = ls.getItem(STORAGE_KEY);
	} catch {
		return {};
	}
	if (raw === null) {
		// First load after upgrade (or a clean browser): try to inherit
		// from the old per-file scheme and clean up its residue.
		return migrateLegacy(ls);
	}
	return parsePrefs(raw);
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
		ls.setItem(STORAGE_KEY, JSON.stringify(merged));
	} catch {
		// best-effort: surface in console only when debugging
	}
}

/** Clear every stored knob for this origin. */
export function clearPrefs(): void {
	const ls = safeStorage();
	if (!ls) return;
	try {
		ls.removeItem(STORAGE_KEY);
	} catch {
		// ignore
	}
}
