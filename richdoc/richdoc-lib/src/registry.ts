/**
 * Browser registry — imports every component's implementation and walks
 * an ordered list of `register()` functions to define the rd-* custom
 * elements.
 *
 * This module references `HTMLElement` transitively, so it MUST NOT be
 * imported by Node/Bun-side code. For schema introspection use
 * `./schema-registry.ts` instead.
 *
 * ## Why is the order list here and not derived from `SCHEMA_BUNDLES`?
 *
 * Importing `SCHEMA_BUNDLES` would transitively pull every component's
 * `spec` (~33 KB of schema strings) into the browser bundle even though
 * the browser never reads them. Keeping the order local lets esbuild
 * tree-shake the spec data out of `richdoc.js`.
 *
 * ## Registration order
 *
 * `customElements.define()` is synchronous and the browser back-fills
 * existing instances with `connectedCallback()` the moment a tag is
 * defined, so ordering between sibling registrations does not affect
 * correctness — only first-paint timing. Two prior optimisations are
 * preserved at the head of the list:
 *
 *   - `rd-prefs` registers before `rd-page` because `RdPage.connectedCallback`
 *     injects a `<rd-prefs>` element; defining the prefs tag first lets
 *     it upgrade in the same microtask.
 *   - `rd-icon` registers before any tag whose `connectedCallback`
 *     constructs `<rd-icon>` children (callouts, checklists, banners …).
 *
 * Everything else follows the canonical vocabulary order documented in
 * `schema-registry.ts`. Adding a new component is a one-line entry here
 * plus the `bundle` export in its `.schema.ts`.
 */

import * as api from "./components/api/api.ts";
import * as badge from "./components/badge/badge.ts";
import * as banner from "./components/banner/banner.ts";
import * as callout from "./components/callout/callout.ts";
import * as card from "./components/card/card.ts";
import * as chart from "./components/chart/chart.ts";
import * as checklist from "./components/checklist/checklist.ts";
import * as code from "./components/code/code.ts";
import * as cols from "./components/cols/cols.ts";
import * as compare from "./components/compare/compare.ts";
import * as decision from "./components/decision/decision.ts";
import * as detail from "./components/detail/detail.ts";
import * as diagram from "./components/diagram/diagram.ts";
import * as diff from "./components/diff/diff.ts";
import * as figure from "./components/figure/figure.ts";
import * as hero from "./components/hero/hero.ts";
import * as icon from "./components/icon/icon.ts";
import * as kv from "./components/kv/kv.ts";
import * as math from "./components/math/math.ts";
import * as page from "./components/page/page.ts";
import * as prefs from "./components/prefs/prefs.ts";
import * as progress from "./components/progress/progress.ts";
import * as prosCons from "./components/pros-cons/pros-cons.ts";
import * as references from "./components/references/references.ts";
import * as rubric from "./components/rubric/rubric.ts";
import * as section from "./components/section/section.ts";
import * as shell from "./components/shell/shell.ts";
import * as stat from "./components/stat/stat.ts";
import * as steps from "./components/steps/steps.ts";
import * as tabs from "./components/tabs/tabs.ts";
import * as timeline from "./components/timeline/timeline.ts";
import * as toc from "./components/toc/toc.ts";
import * as update from "./components/update/update.ts";

export const REGISTRATIONS: ReadonlyArray<() => void> = [
	// First-paint optimisation — see module doc-comment.
	prefs.register,
	page.register,
	icon.register,

	// Structure (vocabulary order from here on).
	hero.register,
	banner.register,
	section.register,
	cols.register,
	card.register,

	// Information blocks
	callout.register,
	kv.register,
	badge.register,
	stat.register,
	progress.register,
	chart.register,
	update.register,

	// Comparison & code
	compare.register,
	rubric.register,
	code.register,
	diff.register,
	shell.register,
	math.register,

	// Sequenced & interactive
	tabs.register,
	timeline.register,
	steps.register,
	detail.register,
	checklist.register,

	// Decision & planning
	decision.register,
	prosCons.register,

	// Reference
	api.register,
	references.register,

	// Diagrams, media, decoration
	diagram.register,
	figure.register,
	toc.register,
];
