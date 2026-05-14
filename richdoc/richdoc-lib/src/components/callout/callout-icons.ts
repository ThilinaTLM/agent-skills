/**
 * Mapping from callout type to a Lucide icon name (resolved via <rd-icon>).
 * Lives here rather than in lib/ so the only consumer (`callout.ts`) owns
 * the data it depends on.
 */
export const CALLOUT_ICONS: Record<string, string> = {
	info: "info",
	success: "check",
	warn: "alert-triangle",
	danger: "x-octagon",
	note: "edit-3",
};
