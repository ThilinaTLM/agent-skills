import { type Upgradeable, define, el } from "../../lib/dom.ts";
import {
	paramSpec,
	paramTagName,
	responseSpec,
	responseTagName,
	spec,
	tagName,
} from "./api.schema.ts";

const PARAM_GROUP_LABELS: Record<string, string> = {
	path: "Path parameters",
	query: "Query parameters",
	header: "Headers",
	body: "Body",
};

const STATUS_TONE: (status: string) => "positive" | "negative" | "neutral" = (status) => {
	const n = parseInt(status, 10);
	if (!Number.isFinite(n)) return "neutral";
	if (n >= 200 && n < 300) return "positive";
	if (n >= 400) return "negative";
	return "neutral";
};

class RdApi extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const method = (this.getAttribute("method") || "GET").toUpperCase();
		const path = this.getAttribute("path") || "";
		const auth = this.getAttribute("auth");
		const title = this.getAttribute("title");
		this.setAttribute("data-method", method);

		const params = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-param"));
		const responses = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-response"));

		this.innerHTML = "";

		const header = el(
			"div",
			{ class: "_rd-api-header" },
			el("span", { class: "_rd-api-method" }, method),
			el("code", { class: "_rd-api-path" }, path),
		);
		this.appendChild(header);

		if (title) this.appendChild(el("div", { class: "_rd-api-title" }, title));
		if (auth) {
			this.appendChild(
				el(
					"div",
					{ class: "_rd-api-auth" },
					el("span", { class: "_rd-api-auth-label" }, "Auth"),
					document.createTextNode(" "),
					el("code", {}, auth),
				),
			);
		}

		// Group params by their `in` attribute. Order: path, query, header, body.
		const groupOrder: Array<keyof typeof PARAM_GROUP_LABELS> = [
			"path",
			"query",
			"header",
			"body",
		];
		const groups = new Map<string, HTMLElement[]>();
		for (const p of params) {
			const where = p.getAttribute("in") || "query";
			if (!groups.has(where)) groups.set(where, []);
			groups.get(where)?.push(p);
		}
		for (const key of groupOrder) {
			const list = groups.get(key);
			if (!list) continue;
			this.appendChild(buildParamGroup(PARAM_GROUP_LABELS[key], list));
		}

		if (responses.length) {
			const block = el(
				"div",
				{ class: "_rd-api-section" },
				el("div", { class: "_rd-api-section-title" }, "Responses"),
			);
			const list = el("div", { class: "_rd-api-responses" });
			for (const r of responses) {
				const status = r.getAttribute("status") || "";
				const type = r.getAttribute("type");
				const row = el(
					"div",
					{ class: "_rd-api-response" },
					el(
						"div",
						{ class: "_rd-api-response-head" },
						el("span", {
							class: "_rd-api-response-status",
							"data-tone": STATUS_TONE(status),
						}, status),
						type ? el("code", { class: "_rd-api-response-type" }, type) : null,
					),
				);
				const body = el("div", { class: "_rd-api-response-body" });
				while (r.firstChild) body.appendChild(r.firstChild);
				row.appendChild(body);
				list.appendChild(row);
			}
			block.appendChild(list);
			this.appendChild(block);
		}
	}
}

function buildParamGroup(label: string, params: HTMLElement[]): HTMLElement {
	const block = el(
		"div",
		{ class: "_rd-api-section" },
		el("div", { class: "_rd-api-section-title" }, label),
	);
	const list = el("div", { class: "_rd-api-params" });
	for (const p of params) {
		const name = p.getAttribute("name") || "";
		const type = p.getAttribute("type");
		const isRequired = p.hasAttribute("required");
		const dflt = p.getAttribute("default");
		const row = el("div", { class: "_rd-api-param" });
		const head = el("div", { class: "_rd-api-param-head" });
		head.appendChild(el("code", { class: "_rd-api-param-name" }, name));
		if (type) head.appendChild(el("span", { class: "_rd-api-param-type" }, type));
		if (isRequired) head.appendChild(el("span", { class: "_rd-api-param-required" }, "required"));
		if (dflt)
			head.appendChild(
				el(
					"span",
					{ class: "_rd-api-param-default" },
					document.createTextNode("default "),
					el("code", {}, dflt),
				),
			);
		row.appendChild(head);
		const body = el("div", { class: "_rd-api-param-body" });
		while (p.firstChild) body.appendChild(p.firstChild);
		row.appendChild(body);
		list.appendChild(row);
	}
	block.appendChild(list);
	return block;
}

class RdParam extends HTMLElement {}
class RdResponse extends HTMLElement {}

export function register(): void {
	define(tagName, RdApi);
	define(paramTagName, RdParam);
	define(responseTagName, RdResponse);
}

export {
	spec,
	tagName,
	paramSpec,
	paramTagName,
	responseSpec,
	responseTagName,
};
