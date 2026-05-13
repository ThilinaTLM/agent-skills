import { define, type Upgradeable } from "../../lib/base.ts";
import { spec, tagName } from "./page.schema.ts";

/**
 * <rd-page> is the only legal child of <body>. It mirrors its `theme`
 * and `mode` attributes onto <html data-theme> / <html data-mode> so the
 * token rules in tokens.css can hang off :root selectors.
 *
 * Precedence (highest to lowest):
 *   1. attribute on <rd-page>
 *   2. attribute already on <html> (set by the doc author directly)
 *   3. system @media (prefers-color-scheme: dark)
 *
 * If <rd-page> has no theme/mode attribute, the existing <html> attrs are
 * left alone — the doc author may set them globally and the page won't
 * stomp on that.
 */
class RdPage extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const theme = this.getAttribute("theme");
		const mode = this.getAttribute("mode");
		if (theme) document.documentElement.setAttribute("data-theme", theme);
		if (mode) document.documentElement.setAttribute("data-mode", mode);
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdPage);
}
export { spec, tagName };
