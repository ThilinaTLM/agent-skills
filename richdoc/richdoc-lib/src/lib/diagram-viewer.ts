/**
 * Shared diagram fullscreen viewer with SVG-native pan/zoom.
 *
 * Built on the native `<dialog>` element so the platform handles focus
 * trap, Esc-to-close, and backdrop. The stage holds a clone of the
 * caller's SVG (or `<img>` fallback) and routes pointer / wheel /
 * keyboard / pinch input into a (tx, ty, scale) state.
 *
 * Two render channels are used deliberately:
 *   - Pan is a CSS `translate(...)` on the wrapper — compositor-fast,
 *     never causes a repaint.
 *   - Zoom is applied by writing pixel `width`/`height` styles onto
 *     the inner SVG so the browser re-paints vector paths at the new
 *     size every frame. The SVG is genuinely never rasterised; glyphs
 *     and lines stay crisp at any zoom.
 *
 * Using CSS `transform: scale()` on a composited wrapper would instead
 * rasterise the SVG once at its 1× layer size and bitmap-scale the
 * result — visibly blurry above ~1.5×. That trap is what this two-
 * channel design avoids.
 *
 * Used by `<rd-mermaid>` and `<rd-plantuml>` via a small corner button
 * each component injects after render. Reused as a singleton: the
 * <dialog> and stage are built on first call and re-used on subsequent
 * opens.
 */

const MIN_SCALE = 0.1;
const MAX_SCALE = 16;
const PAN_KEY_STEP = 40; // px per arrow keystroke
const ZOOM_KEY_STEP = 1.2; // multiplicative factor per + / - keystroke

type Content = SVGElement | HTMLImageElement;

interface State {
	tx: number;
	ty: number;
	scale: number;
	/** Intrinsic content size in CSS pixels — viewBox-derived for SVGs,
	 * natural size for <img>. Cached at open time so applyTransform can
	 * write `width = contentW * scale` without re-measuring. */
	contentW: number;
	contentH: number;
	dragging: boolean;
	pointers: Map<number, { x: number; y: number }>;
	lastPinchDist: number;
	onClose: (() => void) | null;
}

interface ViewerHandles {
	dlg: HTMLDialogElement;
	stage: HTMLElement;
	contentSlot: HTMLElement;
	title: HTMLElement;
	closeBtn: HTMLButtonElement;
}

let handles: ViewerHandles | null = null;
const state: State = {
	tx: 0,
	ty: 0,
	scale: 1,
	contentW: 0,
	contentH: 0,
	dragging: false,
	pointers: new Map(),
	lastPinchDist: 0,
	onClose: null,
};

export interface OpenDiagramViewerOpts {
	/** SVG or image element. Clone before passing — the viewer will move
	 *  the node into its stage and discard on close. */
	content: Content;
	title?: string | null;
	onClose?: () => void;
}

export function openDiagramViewer(opts: OpenDiagramViewerOpts): void {
	const h = ensure();
	state.onClose = opts.onClose ?? null;
	h.title.textContent = opts.title ?? "Diagram";
	h.contentSlot.innerHTML = "";
	// Capture the intrinsic content size once. applyTransform() will
	// write the actual pixel width/height each frame as contentW * scale
	// so the browser re-paints vectors at the new size. We strip any
	// width/height attribute the source carried so the styles we write
	// win without specificity surprises.
	const node = opts.content;
	const size = getContentSize(node);
	state.contentW = size.w;
	state.contentH = size.h;
	if (node instanceof SVGElement) {
		node.removeAttribute("width");
		node.removeAttribute("height");
		node.style.maxWidth = "none";
		node.style.maxHeight = "none";
		node.style.display = "block";
	} else if (node instanceof HTMLImageElement) {
		node.style.maxWidth = "none";
		node.style.maxHeight = "none";
		node.style.display = "block";
		node.draggable = false;
	}
	h.contentSlot.appendChild(node);

	// Reset transform, then fit-to-stage on next frame (after layout has
	// resolved the content's intrinsic box).
	state.tx = 0;
	state.ty = 0;
	state.scale = 1;
	applyTransform();
	if (!h.dlg.open) h.dlg.showModal();
	requestAnimationFrame(() => fit());
}

/** Resolve an intrinsic pixel size for the content. SVGs prefer viewBox
 * → getBBox → bounding rect; images use their natural dimensions. Falls
 * back to a sensible default so fit() never divides by zero. */
function getContentSize(node: Content): { w: number; h: number } {
	if (node instanceof HTMLImageElement) {
		return {
			w: node.naturalWidth || 600,
			h: node.naturalHeight || 400,
		};
	}
	// SVG path.
	const svg = node as SVGSVGElement;
	const vb = svg.viewBox?.baseVal;
	if (vb && vb.width > 0 && vb.height > 0) {
		return { w: vb.width, h: vb.height };
	}
	const wAttr = Number(svg.getAttribute("width")) || 0;
	const hAttr = Number(svg.getAttribute("height")) || 0;
	if (wAttr > 0 && hAttr > 0) return { w: wAttr, h: hAttr };
	try {
		const bb = (svg as unknown as SVGGraphicsElement).getBBox();
		if (bb.width > 0 && bb.height > 0) return { w: bb.width, h: bb.height };
	} catch {
		// getBBox can throw on disconnected SVGs; fall through.
	}
	return { w: 600, h: 400 };
}

function ensure(): ViewerHandles {
	if (handles) return handles;
	const dlg = document.createElement("dialog");
	dlg.className = "_rd-diagram-viewer";
	dlg.setAttribute("aria-label", "Diagram viewer");

	const header = document.createElement("div");
	header.className = "_rd-diagram-viewer-header";

	const title = document.createElement("div");
	title.className = "_rd-diagram-viewer-title";
	header.appendChild(title);

	const toolbar = document.createElement("div");
	toolbar.className = "_rd-diagram-viewer-toolbar";
	const mkBtn = (label: string, ariaLabel: string, onClick: () => void): HTMLButtonElement => {
		const b = document.createElement("button");
		b.type = "button";
		b.className = "_rd-diagram-viewer-btn";
		b.setAttribute("aria-label", ariaLabel);
		b.innerHTML = label;
		b.addEventListener("click", (e) => {
			e.preventDefault();
			onClick();
		});
		return b;
	};
	toolbar.appendChild(mkBtn(ICON_ZOOM_OUT, "Zoom out", () => zoomBy(1 / ZOOM_KEY_STEP)));
	toolbar.appendChild(mkBtn(ICON_ZOOM_IN, "Zoom in", () => zoomBy(ZOOM_KEY_STEP)));
	toolbar.appendChild(mkBtn(ICON_FIT, "Fit to window", () => fit()));
	toolbar.appendChild(mkBtn(ICON_HUNDRED, "Actual size", () => reset100()));
	const closeBtn = mkBtn(ICON_CLOSE, "Close", () => close());
	closeBtn.classList.add("_rd-diagram-viewer-btn-close");
	toolbar.appendChild(closeBtn);
	header.appendChild(toolbar);

	const stage = document.createElement("div");
	stage.className = "_rd-diagram-viewer-stage";
	stage.tabIndex = 0;

	const contentSlot = document.createElement("div");
	contentSlot.className = "_rd-diagram-viewer-content";
	stage.appendChild(contentSlot);

	dlg.appendChild(header);
	dlg.appendChild(stage);
	document.body.appendChild(dlg);

	handles = { dlg, stage, contentSlot, title, closeBtn };
	wireEvents(handles);
	return handles;
}

function wireEvents(h: ViewerHandles): void {
	const { dlg, stage } = h;

	// `<dialog>` closes on Esc by default; mirror our cleanup.
	dlg.addEventListener("close", () => {
		const cb = state.onClose;
		state.onClose = null;
		if (cb) cb();
	});

	// Backdrop click closes (clicks on stage are caught by stage handler).
	dlg.addEventListener("click", (e) => {
		if (e.target === dlg) close();
	});

	// Wheel zoom (around cursor).
	stage.addEventListener(
		"wheel",
		(e) => {
			e.preventDefault();
			const rect = stage.getBoundingClientRect();
			const cx = e.clientX - rect.left;
			const cy = e.clientY - rect.top;
			const factor = Math.exp(-e.deltaY * 0.0015);
			zoomAt(factor, cx, cy);
		},
		{ passive: false },
	);

	// Double-click toggles fit / 100%.
	stage.addEventListener("dblclick", () => {
		if (Math.abs(state.scale - 1) < 0.02) fit();
		else reset100();
	});

	// Pointer pan + pinch zoom. Use PointerEvents so mouse, touch, and
	// pen funnel through one path.
	stage.addEventListener("pointerdown", (e) => {
		stage.setPointerCapture(e.pointerId);
		state.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (state.pointers.size === 1) {
			state.dragging = true;
		} else if (state.pointers.size === 2) {
			state.dragging = false;
			state.lastPinchDist = currentPinchDist();
		}
	});

	stage.addEventListener("pointermove", (e) => {
		const prev = state.pointers.get(e.pointerId);
		if (!prev) return;
		state.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (state.pointers.size === 2) {
			const dist = currentPinchDist();
			if (state.lastPinchDist > 0) {
				const factor = dist / state.lastPinchDist;
				const rect = stage.getBoundingClientRect();
				const mid = pinchMidpoint();
				zoomAt(factor, mid.x - rect.left, mid.y - rect.top);
			}
			state.lastPinchDist = dist;
		} else if (state.dragging && state.pointers.size === 1) {
			state.tx += e.clientX - prev.x;
			state.ty += e.clientY - prev.y;
			applyTransform();
		}
	});

	const endPointer = (e: PointerEvent): void => {
		state.pointers.delete(e.pointerId);
		try {
			stage.releasePointerCapture(e.pointerId);
		} catch {
			// pointer may already be released
		}
		if (state.pointers.size === 0) state.dragging = false;
		if (state.pointers.size < 2) state.lastPinchDist = 0;
	};
	stage.addEventListener("pointerup", endPointer);
	stage.addEventListener("pointercancel", endPointer);

	// Keyboard. The dialog gets focus when opened; we hook on it so any
	// key press while the viewer is open is handled here regardless of
	// which inner control has focus.
	dlg.addEventListener("keydown", (e) => {
		switch (e.key) {
			case "+":
			case "=":
				e.preventDefault();
				zoomBy(ZOOM_KEY_STEP);
				break;
			case "-":
			case "_":
				e.preventDefault();
				zoomBy(1 / ZOOM_KEY_STEP);
				break;
			case "0":
				e.preventDefault();
				fit();
				break;
			case "1":
				e.preventDefault();
				reset100();
				break;
			case "ArrowLeft":
				e.preventDefault();
				state.tx += PAN_KEY_STEP;
				applyTransform();
				break;
			case "ArrowRight":
				e.preventDefault();
				state.tx -= PAN_KEY_STEP;
				applyTransform();
				break;
			case "ArrowUp":
				e.preventDefault();
				state.ty += PAN_KEY_STEP;
				applyTransform();
				break;
			case "ArrowDown":
				e.preventDefault();
				state.ty -= PAN_KEY_STEP;
				applyTransform();
				break;
		}
	});
}

function currentPinchDist(): number {
	const pts = Array.from(state.pointers.values());
	if (pts.length < 2) return 0;
	const dx = pts[0].x - pts[1].x;
	const dy = pts[0].y - pts[1].y;
	return Math.hypot(dx, dy);
}
function pinchMidpoint(): { x: number; y: number } {
	const pts = Array.from(state.pointers.values());
	return { x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2 };
}

function applyTransform(): void {
	if (!handles) return;
	const slot = handles.contentSlot;
	// Pan: compositor-only translate on the wrapper. No repaint.
	slot.style.transform = `translate(${state.tx}px, ${state.ty}px)`;
	// Zoom: write pixel dimensions onto the inner element so the browser
	// re-paints the SVG at the new size (vectors stay crisp) or letter-
	// boxes the <img> (raster still raster, but at least correct shape).
	const inner = slot.firstElementChild as SVGElement | HTMLImageElement | null;
	if (!inner) return;
	const w = state.contentW * state.scale;
	const h = state.contentH * state.scale;
	inner.style.width = `${w}px`;
	inner.style.height = `${h}px`;
}

function clampScale(s: number): number {
	return Math.max(MIN_SCALE, Math.min(MAX_SCALE, s));
}

function zoomBy(factor: number): void {
	if (!handles) return;
	const rect = handles.stage.getBoundingClientRect();
	zoomAt(factor, rect.width / 2, rect.height / 2);
}

function zoomAt(factor: number, cx: number, cy: number): void {
	const next = clampScale(state.scale * factor);
	const real = next / state.scale;
	if (real === 1) return;
	// Keep the point under (cx, cy) stationary across the zoom.
	state.tx = cx - real * (cx - state.tx);
	state.ty = cy - real * (cy - state.ty);
	state.scale = next;
	applyTransform();
}

function fit(): void {
	if (!handles) return;
	const stage = handles.stage;
	const stageRect = stage.getBoundingClientRect();
	const w = state.contentW;
	const h = state.contentH;
	if (w === 0 || h === 0) return;
	const margin = 32;
	const fx = (stageRect.width - margin) / w;
	const fy = (stageRect.height - margin) / h;
	const s = clampScale(Math.min(fx, fy));
	state.scale = s;
	state.tx = (stageRect.width - w * s) / 2;
	state.ty = (stageRect.height - h * s) / 2;
	applyTransform();
}

function reset100(): void {
	if (!handles) return;
	state.scale = 1;
	const stage = handles.stage.getBoundingClientRect();
	const w = state.contentW;
	const h = state.contentH;
	state.tx = (stage.width - w) / 2;
	state.ty = (stage.height - h) / 2;
	applyTransform();
}

function close(): void {
	if (!handles) return;
	if (handles.dlg.open) handles.dlg.close();
}

// Inline Lucide-style glyphs. Keeping these literal instead of pulling
// through rd-icon avoids a CDN round-trip for chrome that's always
// present once the viewer is opened.
const ICON_ZOOM_IN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`;
const ICON_ZOOM_OUT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`;
const ICON_FIT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="4 14 4 20 10 20"/><polyline points="20 10 20 4 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>`;
const ICON_HUNDRED = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><text x="12" y="16" text-anchor="middle" font-family="sans-serif" font-size="9" font-weight="700" stroke="none" fill="currentColor">1:1</text></svg>`;
const ICON_CLOSE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
