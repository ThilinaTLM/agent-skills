/**
 * Inlined Lucide icon core (MIT licensed). These ~30 icons ship inside
 * `richdoc.js` and are guaranteed to render synchronously and offline,
 * so the framework's own components (rd-callout, rd-detail, rd-stat,
 * rd-checklist, rd-tabs, rd-footnote, …) never have to wait on a CDN.
 *
 * Every value is the inner SVG markup for a 24×24 viewBox with the
 * outer <svg stroke="currentColor"> supplied by `<rd-icon>`.
 *
 * Anything outside this list is loaded lazily from jsDelivr at runtime
 * (see `icon-loader.ts`). To add a new core icon, paste the inner markup
 * from `node_modules/lucide-static/icons/<name>.svg` (everything between
 * the opening and closing <svg> tags, stripping the leading license
 * comment and outer attributes).
 *
 * Keep this set small. If an icon is used by the framework itself OR
 * appears in a very high proportion of editorial docs, it earns a slot.
 * Everything else goes through the CDN path.
 */

export const ICONS_CORE: Record<string, string> = {
	// Callout types — required by components/callout/callout-icons.ts CALLOUT_ICONS.
	info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
	check: '<path d="M20 6 9 17l-5-5"/>',
	"alert-triangle":
		'<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
	"x-octagon":
		'<path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86Z"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
	"edit-3": '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/>',

	// Structural / control glyphs used by other components.
	x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
	"chevron-down": '<path d="m6 9 6 6 6-6"/>',
	"chevron-right": '<path d="m9 18 6-6-6-6"/>',
	"arrow-up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
	"arrow-down": '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
	"arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
	"arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
	"external-link":
		'<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
	link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',

	// Most-common editorial glyphs. Inlined so common docs never trigger
	// a CDN round-trip just to render their first paint.
	sparkles:
		'<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>',
	zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
	star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
	bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
	flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>',
	target:
		'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
	shield:
		'<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
	clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
	calendar:
		'<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
	user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
	search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
	"book-open":
		'<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
	"file-text":
		'<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>',
	hash: '<line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/>',
	tag: '<path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"/><path d="M7 7h.01"/>',
	bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
	lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
	eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
};

export type IconCoreName = keyof typeof ICONS_CORE;
