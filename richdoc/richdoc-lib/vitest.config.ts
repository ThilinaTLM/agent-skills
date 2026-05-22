import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for richdoc-lib.
 *
 * The component implementations target the DOM, but the tests we ship
 * today only cover the pure schema layer. We pick the default Node
 * environment for speed; component-DOM tests (jsdom) can be added
 * later when there's something worth covering.
 */
export default defineConfig({
	test: {
		include: ["tests/**/*.test.ts"],
		environment: "node",
	},
});
