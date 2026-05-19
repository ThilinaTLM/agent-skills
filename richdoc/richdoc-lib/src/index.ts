/**
 * richdoc browser entry point.
 *
 * Bundled by `build.ts` as an IIFE (classic script) so it can load over
 * file:// as well as http(s)://. Each component is self-contained; this
 * file just walks the registry and calls each `register()` once.
 */

import { REGISTRATIONS } from "./registry.ts";

for (const r of REGISTRATIONS) r();
