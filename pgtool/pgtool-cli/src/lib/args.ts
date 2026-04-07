/**
 * Common argument definitions shared across all commands.
 */

/** Global args present on every command */
export const globalArgs = {
	root: {
		type: "string" as const,
		alias: "r",
		description:
			"Project root directory (default: auto-detect by walking up to find .pgtool.json)",
	},
	plain: {
		type: "boolean" as const,
		description: "Human-readable output instead of JSON",
	},
	profile: {
		type: "string" as const,
		alias: "p",
		description:
			"Connection profile name (default: from PGTOOL_PROFILE env or config default)",
	},
	"read-only": {
		type: "boolean" as const,
		description: "Force read-only mode regardless of profile config",
	},
	"allow-writes": {
		type: "boolean" as const,
		description: "Override read-only profile config to allow writes",
	},
};

/** Extract init options from parsed args */
export function initOptsFromArgs(args: Record<string, unknown>) {
	return {
		explicitRoot: args.root as string | undefined,
		plain: (args.plain as boolean) ?? false,
		profileName: args.profile as string | undefined,
		readOnly: args["read-only"] as boolean | undefined,
		allowWrites: args["allow-writes"] as boolean | undefined,
	};
}
