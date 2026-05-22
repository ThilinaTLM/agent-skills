import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-api";
export const spec: TagSpec = {
	required: ["method", "path"],
	optional: ["auth", "title"],
	customChildren: ["rd-param", "rd-response"],
	enums: {
		method: ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
	},
};

export const paramTagName = "rd-param";
export const paramSpec: TagSpec = {
	required: ["name"],
	optional: ["in", "required", "type", "default"],
	allowedParents: ["rd-api"],
	customChildren: "any",
	enums: {
		in: ["query", "path", "body", "header"],
	},
};

export const responseTagName = "rd-response";
export const responseSpec: TagSpec = {
	required: ["status"],
	optional: ["type"],
	allowedParents: ["rd-api"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [
		{ tagName: paramTagName, spec: paramSpec },
		{ tagName: responseTagName, spec: responseSpec },
	],
};
