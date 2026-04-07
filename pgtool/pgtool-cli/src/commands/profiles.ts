import { defineCommand } from "citty";
import { loadFileConfig } from "../lib/config.ts";
import {
	formatError,
	formatTable,
	outputError,
	outputJson,
} from "../lib/output.ts";

/**
 * Mask password in a connection URL.
 * postgres://user:secret@host:5432/db → postgres://user:***@host:5432/db
 */
function maskUrlPassword(url: string): string {
	try {
		const parsed = new URL(url);
		if (parsed.password) {
			parsed.password = "***";
		}
		return parsed.toString();
	} catch {
		return url;
	}
}

export const profilesCommand = defineCommand({
	meta: {
		name: "profiles",
		description: "List available connection profiles",
	},
	args: {
		root: {
			type: "string",
			alias: "r",
			description: "Project root directory",
		},
		plain: {
			type: "boolean",
			description: "Human-readable output",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;

		const fileResult = loadFileConfig(args.root);
		if (!fileResult.ok) {
			if (plain) {
				console.error(formatError(fileResult));
				process.exit(1);
			}
			outputError(fileResult);
		}

		const { fileConfig } = fileResult;
		const defaultProfile =
			fileConfig.default || Object.keys(fileConfig.profiles)[0];

		const profiles = Object.entries(fileConfig.profiles).map(
			([name, profile]) => {
				const info: Record<string, unknown> = {
					name,
					default: name === defaultProfile,
				};

				if (profile.url) {
					info.url = maskUrlPassword(profile.url);
				} else {
					info.host = profile.host || null;
					info.port = profile.port || 5432;
					info.database = profile.database || null;
					info.user = profile.user || null;
				}

				info.readOnly = profile.readOnly ?? false;
				info.protected = profile.protected ?? false;

				if (profile.ssl !== undefined) {
					info.ssl = typeof profile.ssl === "object" ? true : profile.ssl;
				}

				return info;
			},
		);

		if (plain) {
			const headers = [
				"Name",
				"Host/URL",
				"Database",
				"User",
				"Default",
				"ReadOnly",
				"Protected",
			];
			const rows = profiles.map((p) => [
				p.name as string,
				(p.url as string) || `${p.host}:${p.port}`,
				(p.database as string) || "-",
				(p.user as string) || "-",
				p.default ? "✓" : "",
				p.readOnly ? "✓" : "",
				p.protected ? "✓" : "",
			]);
			console.log(formatTable(headers, rows));
			process.exit(0);
		}

		outputJson({ ok: true, profiles });
	},
});
