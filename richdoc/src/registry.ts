/**
 * Browser registry — imports every component's implementation and exposes
 * an ordered list of `register()` functions for the entry to call.
 *
 * This module references `HTMLElement` transitively, so it MUST NOT be
 * imported by Node/Bun-side code. For schema introspection use
 * `./schema-registry.ts` instead.
 */

import * as badge from "./components/badge/badge.ts";
import * as callout from "./components/callout/callout.ts";
import * as card from "./components/card/card.ts";
import * as checklist from "./components/checklist/checklist.ts";
import * as code from "./components/code/code.ts";
import * as cols from "./components/cols/cols.ts";
import * as compare from "./components/compare/compare.ts";
import * as defs from "./components/defs/defs.ts";
import * as detail from "./components/detail/detail.ts";
import * as diff from "./components/diff/diff.ts";
import * as figure from "./components/figure/figure.ts";
import * as icon from "./components/icon/icon.ts";
import * as kv from "./components/kv/kv.ts";
import * as math from "./components/math/math.ts";
import * as mermaid from "./components/mermaid/mermaid.ts";
import * as page from "./components/page/page.ts";
import * as quote from "./components/quote/quote.ts";
import * as section from "./components/section/section.ts";
import * as sidenote from "./components/sidenote/sidenote.ts";
import * as stat from "./components/stat/stat.ts";
import * as tabs from "./components/tabs/tabs.ts";
import * as timeline from "./components/timeline/timeline.ts";
import * as toc from "./components/toc/toc.ts";

export const REGISTRATIONS: ReadonlyArray<() => void> = [
	page.register,
	section.register,
	cols.register,
	card.register,
	// icon must register before callout so callout's <rd-icon> children
	// upgrade as soon as they're inserted.
	icon.register,
	callout.register,
	kv.register,
	badge.register,
	compare.register,
	code.register,
	diff.register,
	math.register,
	tabs.register,
	timeline.register,
	mermaid.register,
	toc.register,
	quote.register,
	detail.register,
	stat.register,
	figure.register,
	checklist.register,
	sidenote.register,
	defs.register,
];
