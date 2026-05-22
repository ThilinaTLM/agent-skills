/**
 * Pure schema registry — no DOM imports.
 *
 * Used by `build.ts` (running in Node) to emit `assets/schema.json`,
 * and by the CLI linter at build time. The browser bundle uses
 * `src/registry.ts`, which imports the component implementations as well.
 *
 * Each component's `.schema.ts` declares a `bundle: SchemaBundle` that
 * lists the parent tag + every child tag in one place. This module
 * orders the bundles into the canonical vocabulary order and flat-maps
 * them into a single `SCHEMA_ENTRIES` list. Adding or removing a
 * child tag now touches exactly one file (`.schema.ts` of the parent
 * component), not three (here, `registry.ts`, and the schema file).
 */

import * as api from "./components/api/api.schema.ts";
import * as badge from "./components/badge/badge.schema.ts";
import * as banner from "./components/banner/banner.schema.ts";
import * as callout from "./components/callout/callout.schema.ts";
import * as card from "./components/card/card.schema.ts";
import * as chart from "./components/chart/chart.schema.ts";
import * as checklist from "./components/checklist/checklist.schema.ts";
import * as code from "./components/code/code.schema.ts";
import * as cols from "./components/cols/cols.schema.ts";
import * as compare from "./components/compare/compare.schema.ts";
import * as decision from "./components/decision/decision.schema.ts";
import * as detail from "./components/detail/detail.schema.ts";
import * as diagram from "./components/diagram/diagram.schema.ts";
import * as diff from "./components/diff/diff.schema.ts";
import * as figure from "./components/figure/figure.schema.ts";
import * as hero from "./components/hero/hero.schema.ts";
import * as icon from "./components/icon/icon.schema.ts";
import * as kv from "./components/kv/kv.schema.ts";
import * as math from "./components/math/math.schema.ts";
import * as page from "./components/page/page.schema.ts";
import * as prefs from "./components/prefs/prefs.schema.ts";
import * as progress from "./components/progress/progress.schema.ts";
import * as prosCons from "./components/pros-cons/pros-cons.schema.ts";
import * as references from "./components/references/references.schema.ts";
import * as rubric from "./components/rubric/rubric.schema.ts";
import * as section from "./components/section/section.schema.ts";
import * as shell from "./components/shell/shell.schema.ts";
import * as stat from "./components/stat/stat.schema.ts";
import * as steps from "./components/steps/steps.schema.ts";
import * as tabs from "./components/tabs/tabs.schema.ts";
import * as timeline from "./components/timeline/timeline.schema.ts";
import * as toc from "./components/toc/toc.schema.ts";
import * as update from "./components/update/update.schema.ts";

import type { SchemaBundle, TagEntry } from "./lib/types.ts";

/** Re-export so consumers (CLI linter, docs generators) don't need to
 *  reach into `lib/types.ts` themselves. */
export type { SchemaBundle, TagEntry };

/** Public alias preserved for backwards compatibility with the previous
 *  registry shape. */
export type SchemaEntry = TagEntry;

/** Vocabulary order — drives both `schema.json` order and the SKILL.md
 *  tag reference. Grouping: structure → information blocks → comparison
 *  & code → sequenced & interactive → decision & planning → reference →
 *  diagrams / media / decoration → preview chrome. */
export const SCHEMA_BUNDLES: readonly SchemaBundle[] = [
	// Structure
	page.bundle,
	hero.bundle,
	banner.bundle,
	section.bundle,
	cols.bundle,
	card.bundle,

	// Information blocks
	callout.bundle,
	kv.bundle,
	badge.bundle,
	stat.bundle,
	progress.bundle,
	chart.bundle,
	update.bundle,

	// Comparison & code
	compare.bundle,
	rubric.bundle,
	code.bundle,
	diff.bundle,
	shell.bundle,
	math.bundle,

	// Sequenced & interactive
	tabs.bundle,
	timeline.bundle,
	steps.bundle,
	detail.bundle,
	checklist.bundle,

	// Decision & planning
	decision.bundle,
	prosCons.bundle,

	// Reference
	api.bundle,
	references.bundle,

	// Diagrams, media, decoration
	diagram.bundle,
	figure.bundle,
	toc.bundle,
	icon.bundle,

	// Preview chrome (JS-injected; schema entry only so lint accepts it
	// if someone copies it into source).
	prefs.bundle,
];

/** Flattened parent + child tags in vocabulary order, exactly the
 *  shape `build.ts` needs to emit `assets/schema.json`. */
export const SCHEMA_ENTRIES: readonly TagEntry[] = SCHEMA_BUNDLES.flatMap((b) => [
	{ tagName: b.tagName, spec: b.spec },
	...(b.childTags ?? []),
]);
