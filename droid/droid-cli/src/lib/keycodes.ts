/**
 * Android keycode mappings for common key names.
 */

export const KEY_CODES: Record<string, number> = {
	// Navigation keys (affect app/system)
	back: 4,
	app_home: 3, // KEYCODE_HOME - goes to Android home screen
	home: 3, // Legacy alias (use app_home for clarity)
	menu: 82,
	search: 84,

	// Text editing keys
	enter: 66,
	tab: 61,
	delete: 67,
	del: 67,
	space: 62,

	// Cursor movement keys (for text fields)
	move_home: 122, // KEYCODE_MOVE_HOME - cursor to start of line
	move_end: 123, // KEYCODE_MOVE_END - cursor to end of line
	page_up: 92, // KEYCODE_PAGE_UP
	page_down: 93, // KEYCODE_PAGE_DOWN

	// D-pad / arrow keys
	up: 19,
	down: 20,
	left: 21,
	right: 22,

	// Volume/power
	volup: 24,
	voldown: 25,
	power: 26,

	// Escape
	escape: 111,
	esc: 111,
};
