/**
 * `<rd-prefs>` — floating preview-picker.
 *
 * A small bottom-right control that lets the reader switch theme, mode,
 * and page width at runtime. Auto-injected by `<rd-page>` unless the
 * author opted out with `<rd-page prefs="off">`. Selections persist via
 * `lib/prefs-store.ts` so they survive reloads.
 *
 * The host element is `display: contents`; the painted UI is a fixed
 * floating button + popover panel rendered as children. Hidden in
 * `@media print` by prefs.css.
 *
 * This component is NOT intended for authors to write by hand — but the
 * schema accepts it so a stray copy doesn't break `richdoc lint`.
 */

import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { type Mode, type Theme, type Width, savePrefs } from "../../lib/prefs-store.ts";
import { spec, tagName } from "./prefs.schema.ts";

const THEMES: ReadonlyArray<{ value: Theme; label: string }> = [
	{ value: "editorial-warm", label: "Editorial" },
	{ value: "graphite-modern", label: "Graphite" },
];

const MODES: ReadonlyArray<{ value: Mode; label: string }> = [
	{ value: "light", label: "Light" },
	{ value: "dark", label: "Dark" },
	{ value: "auto", label: "Auto" },
];

const WIDTHS: ReadonlyArray<{ value: Width; label: string }> = [
	{ value: "narrow", label: "Narrow" },
	{ value: "standard", label: "Standard" },
	{ value: "wide", label: "Wide" },
	{ value: "full", label: "Full" },
];

const COG_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33 1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82 1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`;

const CHECK_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>`;

function findPage(): HTMLElement | null {
	return document.querySelector("rd-page");
}

class RdPrefs extends HTMLElement implements Upgradeable {
	_upgraded = false;
	_panel: HTMLElement | null = null;
	_toggle: HTMLButtonElement | null = null;
	_open = false;
	_onDocClick: ((ev: MouseEvent) => void) | null = null;
	_onKeydown: ((ev: KeyboardEvent) => void) | null = null;

	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		this.setAttribute("aria-hidden", "false");

		const toggle = el("button", {
			type: "button",
			class: "_rd-prefs-toggle",
			"aria-label": "Preview settings",
			"aria-haspopup": "dialog",
			"aria-expanded": "false",
			html: COG_SVG,
			onClick: (e: Event) => {
				e.stopPropagation();
				this._togglePanel();
			},
		}) as HTMLButtonElement;
		this._toggle = toggle;
		this.appendChild(toggle);

		const panel = el(
			"div",
			{
				class: "_rd-prefs-panel",
				role: "dialog",
				"aria-label": "Preview settings",
				hidden: true,
			},
			this._buildGroup("Theme", "theme", THEMES, () => this._currentTheme()),
			this._buildGroup("Mode", "mode", MODES, () => this._currentMode()),
			this._buildGroup("Width", "width", WIDTHS, () => this._currentWidth()),
		);
		this._panel = panel;
		this.appendChild(panel);

		// Outside-click + Escape close the panel. Bound on open, removed
		// on close, to keep the document listener footprint minimal when
		// the panel isn't active.
	}

	disconnectedCallback() {
		this._unbindDocHandlers();
	}

	_currentTheme(): Theme {
		const t = document.documentElement.getAttribute("data-theme");
		return t === "graphite-modern" ? "graphite-modern" : "editorial-warm";
	}
	_currentMode(): Mode {
		const m = document.documentElement.getAttribute("data-mode");
		if (m === "light" || m === "dark") return m;
		return "auto";
	}
	_currentWidth(): Width {
		const page = findPage();
		const w = page?.getAttribute("data-width");
		if (w === "narrow" || w === "wide" || w === "full") return w;
		return "standard";
	}

	_buildGroup<T extends string>(
		title: string,
		kind: "theme" | "mode" | "width",
		options: ReadonlyArray<{ value: T; label: string }>,
		getCurrent: () => T,
	): HTMLElement {
		const group = el(
			"div",
			{ class: "_rd-prefs-group", role: "radiogroup", "aria-label": title },
			el("div", { class: "_rd-prefs-group-title" }, title),
		);
		const row = el("div", { class: "_rd-prefs-options" });
		group.appendChild(row);
		const cur = getCurrent();
		for (const opt of options) {
			const isActive = opt.value === cur;
			const btn = el(
				"button",
				{
					type: "button",
					class: "_rd-prefs-option",
					role: "radio",
					"aria-checked": String(isActive),
					"data-active": isActive ? "" : null,
					"data-value": opt.value,
					onClick: () => this._select(kind, opt.value),
				},
				el("span", { class: "_rd-prefs-option-check", html: CHECK_SVG }),
				el("span", { class: "_rd-prefs-option-label" }, opt.label),
			);
			row.appendChild(btn);
		}
		// Mark the group with its kind so re-syncs can find it.
		group.setAttribute("data-kind", kind);
		return group;
	}

	_select(kind: "theme" | "mode" | "width", value: string): void {
		if (kind === "theme") {
			document.documentElement.setAttribute("data-theme", value);
			savePrefs({ theme: value as Theme });
		} else if (kind === "mode") {
			// `auto` clears the explicit attribute so the OS @media
			// fallback applies; light/dark pin it.
			if (value === "auto") {
				document.documentElement.removeAttribute("data-mode");
			} else {
				document.documentElement.setAttribute("data-mode", value);
			}
			savePrefs({ mode: value as Mode });
		} else if (kind === "width") {
			const page = findPage();
			if (page) page.setAttribute("data-width", value);
			savePrefs({ width: value as Width });
		}
		this._resyncGroup(kind);
	}

	/** After a click, refresh the `aria-checked` + active state of the
	 * just-changed group. Cheap rather than re-rendering the panel. */
	_resyncGroup(kind: "theme" | "mode" | "width"): void {
		if (!this._panel) return;
		const group = this._panel.querySelector<HTMLElement>(`._rd-prefs-group[data-kind="${kind}"]`);
		if (!group) return;
		const cur =
			kind === "theme"
				? this._currentTheme()
				: kind === "mode"
					? this._currentMode()
					: this._currentWidth();
		for (const btn of group.querySelectorAll<HTMLElement>("._rd-prefs-option")) {
			const v = btn.getAttribute("data-value");
			const active = v === cur;
			btn.setAttribute("aria-checked", String(active));
			if (active) btn.setAttribute("data-active", "");
			else btn.removeAttribute("data-active");
		}
	}

	_togglePanel(): void {
		this._open ? this._closePanel() : this._openPanel();
	}
	_openPanel(): void {
		if (!this._panel || !this._toggle) return;
		this._panel.hidden = false;
		this._toggle.setAttribute("aria-expanded", "true");
		this._open = true;
		this.setAttribute("data-open", "");
		this._bindDocHandlers();
	}
	_closePanel(): void {
		if (!this._panel || !this._toggle) return;
		this._panel.hidden = true;
		this._toggle.setAttribute("aria-expanded", "false");
		this._open = false;
		this.removeAttribute("data-open");
		this._unbindDocHandlers();
	}

	_bindDocHandlers(): void {
		this._onDocClick = (ev: MouseEvent) => {
			if (!this._panel || !this._toggle) return;
			const t = ev.target as Node | null;
			if (!t) return;
			if (this._panel.contains(t) || this._toggle.contains(t)) return;
			this._closePanel();
		};
		this._onKeydown = (ev: KeyboardEvent) => {
			if (ev.key === "Escape") {
				this._closePanel();
				this._toggle?.focus();
			}
		};
		document.addEventListener("click", this._onDocClick, true);
		document.addEventListener("keydown", this._onKeydown);
	}
	_unbindDocHandlers(): void {
		if (this._onDocClick) {
			document.removeEventListener("click", this._onDocClick, true);
			this._onDocClick = null;
		}
		if (this._onKeydown) {
			document.removeEventListener("keydown", this._onKeydown);
			this._onKeydown = null;
		}
	}
}

export function register(): void {
	define(tagName, RdPrefs);
}
export { spec, tagName };
