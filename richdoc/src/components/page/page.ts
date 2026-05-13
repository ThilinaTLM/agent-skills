import { define } from "../../lib/base.ts";
import { spec, tagName } from "./page.schema.ts";

class RdPage extends HTMLElement {
	connectedCallback() {
		const theme = this.getAttribute("theme");
		if (theme === "light" || theme === "dark") {
			document.documentElement.setAttribute("data-theme", theme);
		}
	}
}

export function register(): void {
	define(tagName, RdPage);
}
export { spec, tagName };
