/**
 * Pure schema registry — no DOM imports.
 *
 * Used by `build.ts` (running in Node) to emit `assets/schema.json`,
 * and by the CLI linter at build time. The browser bundle uses
 * `src/registry.ts`, which imports the component implementations as well.
 *
 * Order here defines the order in `schema.json` and the order in the
 * generated tag reference.
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

import type { TagSpec } from "./lib/types.ts";

export interface SchemaEntry {
	readonly tagName: string;
	readonly spec: TagSpec;
}

/** Vocabulary order — drives both schema.json order and SKILL.md tag reference.
 * Grouped: structure, information blocks, comparison & code, sequenced &
 * interactive, decoration & inline. */
export const SCHEMA_ENTRIES: readonly SchemaEntry[] = [
	// Structure
	{ tagName: page.tagName, spec: page.spec },
	{ tagName: hero.tagName, spec: hero.spec },
	{ tagName: banner.tagName, spec: banner.spec },
	{ tagName: section.tagName, spec: section.spec },
	{ tagName: cols.tagName, spec: cols.spec },
	{ tagName: card.tagName, spec: card.spec },

	// Information blocks
	{ tagName: callout.tagName, spec: callout.spec },
	{ tagName: kv.tagName, spec: kv.spec },
	{ tagName: kv.rowTagName, spec: kv.rowSpec },
	{ tagName: badge.tagName, spec: badge.spec },
	{ tagName: stat.tagName, spec: stat.spec },
	{ tagName: progress.tagName, spec: progress.spec },
	{ tagName: chart.tagName, spec: chart.spec },
	{ tagName: update.tagName, spec: update.spec },

	// Comparison & code
	{ tagName: compare.tagName, spec: compare.spec },
	{ tagName: compare.rowCellsTagName, spec: compare.rowCellsSpec },
	{ tagName: compare.cellTagName, spec: compare.cellSpec },
	{ tagName: rubric.tagName, spec: rubric.spec },
	{ tagName: rubric.criterionTagName, spec: rubric.criterionSpec },
	{ tagName: rubric.scoreTagName, spec: rubric.scoreSpec },
	{ tagName: code.tagName, spec: code.spec },
	{ tagName: diff.tagName, spec: diff.spec },
	{ tagName: shell.tagName, spec: shell.spec },
	{ tagName: shell.promptTagName, spec: shell.promptSpec },
	{ tagName: shell.outputTagName, spec: shell.outputSpec },
	{ tagName: math.tagName, spec: math.spec },

	// Sequenced & interactive
	{ tagName: tabs.tagName, spec: tabs.spec },
	{ tagName: tabs.tabTagName, spec: tabs.tabSpec },
	{ tagName: timeline.tagName, spec: timeline.spec },
	{ tagName: timeline.eventTagName, spec: timeline.eventSpec },
	{ tagName: steps.tagName, spec: steps.spec },
	{ tagName: steps.stepTagName, spec: steps.stepSpec },
	{ tagName: detail.tagName, spec: detail.spec },
	{ tagName: checklist.tagName, spec: checklist.spec },
	{ tagName: checklist.taskTagName, spec: checklist.taskSpec },

	// Decision & planning
	{ tagName: decision.tagName, spec: decision.spec },
	{ tagName: prosCons.tagName, spec: prosCons.spec },
	{ tagName: prosCons.proTagName, spec: prosCons.proSpec },
	{ tagName: prosCons.conTagName, spec: prosCons.conSpec },

	// Reference
	{ tagName: api.tagName, spec: api.spec },
	{ tagName: api.paramTagName, spec: api.paramSpec },
	{ tagName: api.responseTagName, spec: api.responseSpec },
	{ tagName: references.tagName, spec: references.spec },
	{ tagName: references.refTagName, spec: references.refSpec },
	{ tagName: references.citeTagName, spec: references.citeSpec },

	// Diagrams, media, decoration
	{ tagName: diagram.tagName, spec: diagram.spec },
	{ tagName: figure.tagName, spec: figure.spec },
	{ tagName: toc.tagName, spec: toc.spec },
	{ tagName: toc.chapterTagName, spec: toc.chapterSpec },
	{ tagName: icon.tagName, spec: icon.spec },

	// Preview chrome (JS-injected, schema entry only so lint accepts it
	// if someone copies it into source).
	{ tagName: prefs.tagName, spec: prefs.spec },
];
