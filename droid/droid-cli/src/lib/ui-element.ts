/**
 * UIElement class representing a parsed UI element from the hierarchy dump.
 */

import type { UIElementData } from "../types";

export class UIElement {
	text: string;
	className: string;
	resourceId: string;
	contentDesc: string;
	clickable: boolean;
	boundsStr: string;

	x1: number;
	y1: number;
	x2: number;
	y2: number;
	x: number;
	y: number;

	constructor(node: Record<string, string>) {
		this.text = node["@_text"] || "";
		this.className = (node["@_class"] || "").split(".").pop() || "";
		const rawId = node["@_resource-id"] || "";
		this.resourceId = rawId.includes("/")
			? rawId.split("/").pop() || ""
			: rawId;
		this.contentDesc = node["@_content-desc"] || "";
		this.clickable = node["@_clickable"] === "true";
		this.boundsStr = node["@_bounds"] || "";

		// Parse bounds [x1,y1][x2,y2]
		this.x1 = this.y1 = this.x2 = this.y2 = 0;
		this.x = this.y = 0;

		const match = this.boundsStr.match(/\[(\d+),(\d+)\]\[(\d+),(\d+)\]/);
		if (match) {
			this.x1 = Number.parseInt(match[1], 10);
			this.y1 = Number.parseInt(match[2], 10);
			this.x2 = Number.parseInt(match[3], 10);
			this.y2 = Number.parseInt(match[4], 10);
			this.x = Math.floor((this.x1 + this.x2) / 2);
			this.y = Math.floor((this.y1 + this.y2) / 2);
		}
	}

	/**
	 * Check if element matches a text query.
	 */
	matches(query: string): boolean {
		const queryLower = query.toLowerCase();
		return (
			this.text.toLowerCase().includes(queryLower) ||
			this.contentDesc.toLowerCase().includes(queryLower) ||
			this.resourceId.toLowerCase().includes(queryLower)
		);
	}

	/**
	 * Check if element has no identifying information.
	 */
	isEmpty(): boolean {
		return !this.text && !this.resourceId && !this.contentDesc;
	}

	/**
	 * Check if element is an input field.
	 */
	isInputField(): boolean {
		return ["EditText", "TextInputEditText", "AutoCompleteTextView"].includes(
			this.className,
		);
	}

	/**
	 * Convert to dictionary for JSON output.
	 */
	toDict(): UIElementData {
		return {
			text: this.text,
			class: this.className,
			id: this.resourceId,
			desc: this.contentDesc,
			clickable: this.clickable,
			x: this.x,
			y: this.y,
			bounds: [this.x1, this.y1, this.x2, this.y2],
		};
	}
}
