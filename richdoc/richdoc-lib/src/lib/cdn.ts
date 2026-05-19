/**
 * Shared CDN asset loaders. Used by `<rd-code>` (highlight.js), `<rd-math>`
 * (KaTeX), and `<rd-mermaid>` (mermaid). Each loader is idempotent and
 * shares one in-flight promise per URL.
 */

const cdnLoaders = new Map<string, Promise<unknown>>();

/**
 * Shared CDN script loader. Resolves to the global your code exposes
 * (e.g. window.mermaid, window.katex, window.hljs) or null on failure.
 * Idempotent: parallel calls for the same URL share a single promise.
 */
export function loadCdnScript<T = unknown>(
	url: string,
	getGlobal: () => T | undefined,
): Promise<T | null> {
	const existing = cdnLoaders.get(url) as Promise<T | null> | undefined;
	if (existing) return existing;
	const p = new Promise<T | null>((resolve) => {
		const already = getGlobal();
		if (already) return resolve(already);
		const s = document.createElement("script");
		s.src = url;
		s.async = true;
		s.onload = () => resolve(getGlobal() ?? null);
		s.onerror = () => {
			console.warn(`[richdoc] CDN script load failed: ${url}`);
			resolve(null);
		};
		document.head.appendChild(s);
	});
	cdnLoaders.set(url, p);
	return p;
}

/** Inject a stylesheet from a CDN once. Tagged to avoid duplicates. */
export function loadCdnStyle(url: string): void {
	if (document.querySelector(`link[data-rd-cdn="${url}"]`)) return;
	const l = document.createElement("link");
	l.rel = "stylesheet";
	l.href = url;
	l.setAttribute("data-rd-cdn", url);
	document.head.appendChild(l);
}
