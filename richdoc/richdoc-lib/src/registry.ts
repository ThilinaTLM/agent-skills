/**
 * Browser registry — imports every component's implementation and exposes
 * an ordered list of `register()` functions for the entry to call.
 *
 * This module references `HTMLElement` transitively, so it MUST NOT be
 * imported by Node/Bun-side code. For schema introspection use
 * `./schema-registry.ts` instead.
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
import * as diff from "./components/diff/diff.ts";
import * as embed from "./components/embed/embed.ts";
import * as figure from "./components/figure/figure.ts";
import * as footnote from "./components/footnote/footnote.ts";
import * as gallery from "./components/gallery/gallery.ts";
import * as hero from "./components/hero/hero.ts";
import * as icon from "./components/icon/icon.ts";
import * as kv from "./components/kv/kv.ts";
import * as math from "./components/math/math.ts";
import * as mermaid from "./components/mermaid/mermaid.ts";
import * as page from "./components/page/page.ts";
import * as plantuml from "./components/plantuml/plantuml.ts";
import * as prefs from "./components/prefs/prefs.ts";
import * as progress from "./components/progress/progress.ts";
import * as prosCons from "./components/pros-cons/pros-cons.ts";
import * as quote from "./components/quote/quote.ts";
import * as references from "./components/references/references.ts";
import * as roadmap from "./components/roadmap/roadmap.ts";
import * as rubric from "./components/rubric/rubric.ts";
import * as section from "./components/section/section.ts";
import * as shell from "./components/shell/shell.ts";
import * as stat from "./components/stat/stat.ts";
import * as steps from "./components/steps/steps.ts";
import * as swatch from "./components/swatch/swatch.ts";
import * as tabs from "./components/tabs/tabs.ts";
import * as timeline from "./components/timeline/timeline.ts";
import * as toc from "./components/toc/toc.ts";
import * as tooltip from "./components/tooltip/tooltip.ts";
import * as tree from "./components/tree/tree.ts";
import * as update from "./components/update/update.ts";

export const REGISTRATIONS: ReadonlyArray<() => void> = [
	// `prefs` must register before `page` because page.ts injects a
	// <rd-prefs> element at upgrade time and we want it to upgrade
	// immediately rather than wait for the registry walk to come back
	// round.
	prefs.register,
	page.register,
	section.register,
	cols.register,
	card.register,
	// icon must register before any tag that constructs <rd-icon> children,
	// so those children upgrade as soon as they're inserted.
	icon.register,
	callout.register,
	banner.register,
	hero.register,
	kv.register,
	badge.register,
	compare.register,
	rubric.register,
	code.register,
	diff.register,
	shell.register,
	math.register,
	tabs.register,
	timeline.register,
	steps.register,
	prosCons.register,
	update.register,
	decision.register,
	mermaid.register,
	plantuml.register,
	roadmap.register,
	toc.register,
	quote.register,
	detail.register,
	tree.register,
	stat.register,
	progress.register,
	chart.register,
	figure.register,
	swatch.register,
	gallery.register,
	embed.register,
	checklist.register,
	api.register,
	// tooltip must register before footnote so the footnote marker can
	// rely on the shared tooltip layer being available at upgrade time.
	tooltip.register,
	footnote.register,
	references.register,
];
