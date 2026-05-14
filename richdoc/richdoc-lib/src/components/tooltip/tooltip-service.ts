/**
 * Tooltip helper — owns the floating popup layer, event wiring, ARIA, and
 * positioning. Used by <rd-tooltip> for author-attached previews and by
 * <rd-footnote> to give its inline marker a hover preview of the bottom-
 * of-page entry.
 *
 * Design notes:
 *   - One shared `<div class="_rd-tooltip-layer">` lives in <body> and
 *     hosts the popup element of whichever tooltip is currently visible.
 *     Only one popup is shown at a time.
 *   - Positioning is computed in JS (no CSS Anchor Positioning) so the
 *     helper works in every browser the rest of richdoc supports.
 *   - The popup is `position: fixed`, so page scroll does not require
 *     offset math; scroll/resize listeners just re-run the placement.
 *   - The caller owns the content lifecycle. Pass a cloned node if the
 *     same content is referenced elsewhere (e.g. footnotes preserve the
 *     canonical entry at the foot of the page).
 */

export interface TooltipOptions {
	/** Whether tap/click on the trigger toggles the tooltip (true) or is
	 *  left alone for the trigger's native behaviour, such as link
	 *  navigation (false). Hover and focus always show the tooltip
	 *  regardless. */
	clickToToggle?: boolean;
	/** Preferred placement; the helper auto-flips on viewport overflow.
	 *  "auto" prefers bottom and flips to top on overflow. */
	placement?: "auto" | "top" | "bottom";
	/** Optional class added to the popup element for component-specific
	 *  styling hooks (e.g. "_rd-fn-preview" on the footnote variant). */
	popupClass?: string;
}

interface ActiveTooltip {
	trigger: HTMLElement;
	popup: HTMLElement;
	content: HTMLElement;
	opts: Required<Pick<TooltipOptions, "clickToToggle" | "placement">> & {
		popupClass?: string;
	};
	showTimer: number | null;
	hideTimer: number | null;
	visible: boolean;
}

let nextId = 1;
let sharedLayer: HTMLElement | null = null;
let currentVisible: ActiveTooltip | null = null;

// Active tooltip records keyed by trigger so repeat calls replace cleanly.
const registered = new WeakMap<HTMLElement, ActiveTooltip>();

const SHOW_DELAY_MS = 120;
const HIDE_DELAY_MS = 80;
const GAP_PX = 8;
const VIEWPORT_PADDING_PX = 8;
const ARROW_INSET_PX = 12;

function getLayer(): HTMLElement {
	if (sharedLayer?.isConnected) return sharedLayer;
	const layer = document.createElement("div");
	layer.className = "_rd-tooltip-layer";
	layer.setAttribute("role", "presentation");
	document.body.appendChild(layer);
	sharedLayer = layer;
	return layer;
}

function buildPopup(content: HTMLElement, popupClass: string | undefined, id: string): HTMLElement {
	const popup = document.createElement("div");
	popup.setAttribute("role", "tooltip");
	popup.id = id;
	if (popupClass) popup.classList.add(popupClass);
	popup.appendChild(content);
	return popup;
}

function clearTimers(record: ActiveTooltip) {
	if (record.showTimer !== null) {
		window.clearTimeout(record.showTimer);
		record.showTimer = null;
	}
	if (record.hideTimer !== null) {
		window.clearTimeout(record.hideTimer);
		record.hideTimer = null;
	}
}

function position(record: ActiveTooltip) {
	const { trigger, popup, opts } = record;
	const triggerRect = trigger.getBoundingClientRect();
	// Reset any placement-specific data attr so the measurement reflects
	// the popup's natural size, not the previous arrow geometry.
	popup.style.maxWidth = "";
	const popupRect = popup.getBoundingClientRect();
	const vw = window.innerWidth;
	const vh = window.innerHeight;

	// Decide vertical placement.
	const spaceBelow = vh - triggerRect.bottom - GAP_PX - VIEWPORT_PADDING_PX;
	const spaceAbove = triggerRect.top - GAP_PX - VIEWPORT_PADDING_PX;
	let placement: "top" | "bottom";
	if (opts.placement === "top") placement = "top";
	else if (opts.placement === "bottom") placement = "bottom";
	else placement = popupRect.height <= spaceBelow || spaceBelow >= spaceAbove ? "bottom" : "top";

	const top =
		placement === "bottom"
			? triggerRect.bottom + GAP_PX
			: triggerRect.top - popupRect.height - GAP_PX;

	// Horizontal: centre on the trigger, then clamp to viewport.
	const triggerCenter = triggerRect.left + triggerRect.width / 2;
	const idealLeft = triggerCenter - popupRect.width / 2;
	const maxLeft = vw - popupRect.width - VIEWPORT_PADDING_PX;
	const left = Math.max(VIEWPORT_PADDING_PX, Math.min(idealLeft, maxLeft));

	// Arrow position relative to popup, clamped so it stays within edges.
	const arrowX = Math.max(
		ARROW_INSET_PX,
		Math.min(triggerCenter - left, popupRect.width - ARROW_INSET_PX),
	);

	popup.style.top = `${Math.round(top)}px`;
	popup.style.left = `${Math.round(left)}px`;
	popup.style.setProperty("--rd-tt-arrow-x", `${Math.round(arrowX)}px`);
	popup.setAttribute("data-placement", placement);
}

function onScrollOrResize() {
	if (currentVisible) position(currentVisible);
}

function onDocumentPointerDown(ev: PointerEvent) {
	if (!currentVisible) return;
	const target = ev.target as Node | null;
	if (!target) return;
	if (currentVisible.popup.contains(target)) return;
	if (currentVisible.trigger.contains(target)) return;
	hide(currentVisible, /* immediate */ true);
}

function attachGlobalListeners() {
	window.addEventListener("scroll", onScrollOrResize, { passive: true, capture: true });
	window.addEventListener("resize", onScrollOrResize, { passive: true });
	document.addEventListener("pointerdown", onDocumentPointerDown, true);
}

function detachGlobalListeners() {
	window.removeEventListener("scroll", onScrollOrResize, { capture: true });
	window.removeEventListener("resize", onScrollOrResize);
	document.removeEventListener("pointerdown", onDocumentPointerDown, true);
}

function show(record: ActiveTooltip) {
	clearTimers(record);
	if (currentVisible && currentVisible !== record) {
		hide(currentVisible, /* immediate */ true);
	}
	const layer = getLayer();
	if (record.popup.parentElement !== layer) {
		layer.appendChild(record.popup);
	}
	record.visible = true;
	currentVisible = record;
	// Position once before reveal so the first frame is already correct.
	position(record);
	// Force a layout read so the transition triggers reliably.
	void record.popup.offsetWidth;
	record.popup.setAttribute("data-visible", "");
	record.trigger.setAttribute("aria-describedby", record.popup.id);
	attachGlobalListeners();
}

function hide(record: ActiveTooltip, immediate = false) {
	clearTimers(record);
	if (!record.visible) return;
	record.visible = false;
	record.popup.removeAttribute("data-visible");
	record.trigger.removeAttribute("aria-describedby");
	if (currentVisible === record) currentVisible = null;
	detachGlobalListeners();
	if (immediate) {
		if (record.popup.parentElement) record.popup.parentElement.removeChild(record.popup);
	} else {
		// Remove from DOM after the fade-out so screen readers don't keep
		// announcing it. The transition duration in CSS is 120ms.
		window.setTimeout(() => {
			if (!record.visible && record.popup.parentElement) {
				record.popup.parentElement.removeChild(record.popup);
			}
		}, 160);
	}
}

function scheduleShow(record: ActiveTooltip, delay = SHOW_DELAY_MS) {
	clearTimers(record);
	if (record.visible) return;
	record.showTimer = window.setTimeout(() => {
		record.showTimer = null;
		show(record);
	}, delay);
}

function scheduleHide(record: ActiveTooltip, delay = HIDE_DELAY_MS) {
	clearTimers(record);
	if (!record.visible && record.showTimer === null) return;
	record.hideTimer = window.setTimeout(() => {
		record.hideTimer = null;
		hide(record);
	}, delay);
}

/**
 * Attach a tooltip to a trigger element. Idempotent per trigger: a second
 * call replaces the previous content and options.
 */
export function attachTooltip(
	trigger: HTMLElement,
	content: Node | string,
	opts: TooltipOptions = {},
): void {
	// Replace any prior registration on this trigger.
	const existing = registered.get(trigger);
	if (existing) {
		hide(existing, /* immediate */ true);
		registered.delete(trigger);
	}

	const contentEl =
		content instanceof HTMLElement
			? content
			: content instanceof Node
				? (() => {
						const wrap = document.createElement("div");
						wrap.appendChild(content);
						return wrap;
					})()
				: (() => {
						const wrap = document.createElement("div");
						wrap.textContent = String(content);
						return wrap;
					})();
	contentEl.classList.add("_rd-tooltip-content");

	const id = `rd-tt-${nextId++}`;
	const popup = buildPopup(contentEl, opts.popupClass, id);

	const record: ActiveTooltip = {
		trigger,
		popup,
		content: contentEl,
		opts: {
			clickToToggle: opts.clickToToggle ?? true,
			placement: opts.placement ?? "auto",
			popupClass: opts.popupClass,
		},
		showTimer: null,
		hideTimer: null,
		visible: false,
	};
	registered.set(trigger, record);

	// Trigger interactions.
	trigger.addEventListener("mouseenter", () => scheduleShow(record));
	trigger.addEventListener("mouseleave", () => scheduleHide(record));
	trigger.addEventListener("focusin", () => {
		clearTimers(record);
		show(record);
	});
	trigger.addEventListener("focusout", () => {
		clearTimers(record);
		hide(record);
	});
	trigger.addEventListener("keydown", (ev) => {
		if (ev.key === "Escape" && record.visible) {
			ev.stopPropagation();
			hide(record, /* immediate */ true);
			trigger.focus();
		}
	});
	trigger.addEventListener("click", (ev) => {
		if (!record.opts.clickToToggle) return;
		// On click-to-toggle triggers, prevent any default (e.g. an <a
		// href="#"> from navigating) and toggle visibility.
		ev.preventDefault();
		if (record.visible) hide(record, /* immediate */ true);
		else show(record);
	});

	// Popup interactions — keep open while the cursor is over it.
	popup.addEventListener("mouseenter", () => clearTimers(record));
	popup.addEventListener("mouseleave", () => scheduleHide(record));
}
