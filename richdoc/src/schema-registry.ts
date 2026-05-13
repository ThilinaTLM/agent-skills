/**
 * Pure schema registry — no DOM imports.
 *
 * Used by `build.ts` (running in Bun / Node) to emit `assets/schema.json`,
 * and by the CLI linter at build time. The browser bundle uses
 * `src/registry.ts`, which imports the component implementations as well.
 *
 * Order here defines the order in `schema.json` and the order in the
 * generated tag reference.
 */

import * as badge from "./components/badge/badge.schema.ts";
import * as callout from "./components/callout/callout.schema.ts";
import * as card from "./components/card/card.schema.ts";
import * as checklist from "./components/checklist/checklist.schema.ts";
import * as code from "./components/code/code.schema.ts";
import * as cols from "./components/cols/cols.schema.ts";
import * as compare from "./components/compare/compare.schema.ts";
import * as detail from "./components/detail/detail.schema.ts";
import * as figure from "./components/figure/figure.schema.ts";
import * as kv from "./components/kv/kv.schema.ts";
import * as mermaid from "./components/mermaid/mermaid.schema.ts";
import * as page from "./components/page/page.schema.ts";
import * as quote from "./components/quote/quote.schema.ts";
import * as section from "./components/section/section.schema.ts";
import * as stat from "./components/stat/stat.schema.ts";
import * as tabs from "./components/tabs/tabs.schema.ts";
import * as timeline from "./components/timeline/timeline.schema.ts";
import * as toc from "./components/toc/toc.schema.ts";

import type { TagSpec } from "./lib/types.ts";

export interface SchemaEntry {
	readonly tagName: string;
	readonly spec: TagSpec;
}

/** Vocabulary order — drives both schema.json order and SKILL.md tag reference. */
export const SCHEMA_ENTRIES: readonly SchemaEntry[] = [
	{ tagName: page.tagName, spec: page.spec },
	{ tagName: section.tagName, spec: section.spec },
	{ tagName: cols.tagName, spec: cols.spec },
	{ tagName: card.tagName, spec: card.spec },
	{ tagName: callout.tagName, spec: callout.spec },
	{ tagName: kv.tagName, spec: kv.spec },
	{ tagName: kv.rowTagName, spec: kv.rowSpec },
	{ tagName: badge.tagName, spec: badge.spec },
	{ tagName: compare.tagName, spec: compare.spec },
	{ tagName: compare.rowCellsTagName, spec: compare.rowCellsSpec },
	{ tagName: compare.cellTagName, spec: compare.cellSpec },
	{ tagName: code.tagName, spec: code.spec },
	{ tagName: tabs.tagName, spec: tabs.spec },
	{ tagName: tabs.tabTagName, spec: tabs.tabSpec },
	{ tagName: timeline.tagName, spec: timeline.spec },
	{ tagName: timeline.eventTagName, spec: timeline.eventSpec },
	{ tagName: mermaid.tagName, spec: mermaid.spec },
	{ tagName: toc.tagName, spec: toc.spec },
	{ tagName: quote.tagName, spec: quote.spec },
	{ tagName: detail.tagName, spec: detail.spec },
	{ tagName: stat.tagName, spec: stat.spec },
	{ tagName: figure.tagName, spec: figure.spec },
	{ tagName: checklist.tagName, spec: checklist.spec },
	{ tagName: checklist.taskTagName, spec: checklist.taskSpec },
];
