import { defineCommand } from "citty";
import {
	ensureDaemon,
	getDaemonStatus,
	shutdownDaemon,
} from "../daemon/client.ts";
import { isDaemonRunning } from "../daemon/pid.ts";
import { getSocketPath } from "../daemon/socket-path.ts";
import { formatTable, outputJson } from "../lib/output.ts";

const startCommand = defineCommand({
	meta: {
		name: "start",
		description: "Start the pgtool daemon (or confirm it is running)",
	},
	args: {
		plain: {
			type: "boolean",
			description: "Human-readable output",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;
		const started = await ensureDaemon();

		if (!started) {
			const response = {
				ok: false,
				error: "Failed to start daemon",
				code: "CONNECTION_FAILED",
				hint: "Check that the socket directory is writable and no conflicting process exists",
			};
			if (plain) {
				console.error(`Error: ${response.error}`);
				process.exit(1);
			}
			outputJson(response, 1);
		}

		const status = await getDaemonStatus();
		if (status && "pid" in status) {
			const response = {
				ok: true,
				message: "Daemon is running",
				pid: status.pid,
				socket: getSocketPath(),
			};
			if (plain) {
				console.log(`Daemon running (PID ${status.pid}) at ${getSocketPath()}`);
				process.exit(0);
			}
			outputJson(response);
		} else {
			const response = {
				ok: true,
				message: "Daemon started",
				socket: getSocketPath(),
			};
			if (plain) {
				console.log(`Daemon started at ${getSocketPath()}`);
				process.exit(0);
			}
			outputJson(response);
		}
	},
});

const stopCommand = defineCommand({
	meta: {
		name: "stop",
		description: "Stop the pgtool daemon",
	},
	args: {
		plain: {
			type: "boolean",
			description: "Human-readable output",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;

		const { running, pid } = isDaemonRunning();
		if (!running) {
			const response = {
				ok: true,
				message: "Daemon is not running",
			};
			if (plain) {
				console.log("Daemon is not running");
				process.exit(0);
			}
			outputJson(response);
			return;
		}

		const stopped = await shutdownDaemon();
		if (stopped) {
			const response = {
				ok: true,
				message: "Daemon stopped",
				pid,
			};
			if (plain) {
				console.log(`Daemon stopped (was PID ${pid})`);
				process.exit(0);
			}
			outputJson(response);
		} else {
			const response = {
				ok: false,
				error: "Failed to stop daemon",
				code: "CONNECTION_FAILED",
				hint: `Try killing the process manually: kill ${pid}`,
			};
			if (plain) {
				console.error(`Error: Failed to stop daemon (PID ${pid})`);
				process.exit(1);
			}
			outputJson(response, 1);
		}
	},
});

const statusCommand = defineCommand({
	meta: {
		name: "status",
		description: "Show daemon status and connection pool info",
	},
	args: {
		plain: {
			type: "boolean",
			description: "Human-readable output",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;

		const { running, pid } = isDaemonRunning();
		if (!running) {
			const response = {
				ok: true,
				running: false,
				socket: getSocketPath(),
			};
			if (plain) {
				console.log("Daemon is not running");
				process.exit(0);
			}
			outputJson(response);
			return;
		}

		const status = await getDaemonStatus();
		if (!status || !("pid" in status)) {
			const response = {
				ok: true,
				running: true,
				pid,
				note: "Daemon is running but did not respond to status request",
			};
			if (plain) {
				console.log(`Daemon running (PID ${pid}) but not responding`);
				process.exit(0);
			}
			outputJson(response);
			return;
		}

		const response = {
			ok: true,
			running: true,
			pid: status.pid,
			uptime: status.uptime,
			socket: status.socket,
			pools: status.pools,
		};

		if (plain) {
			const uptime = formatUptime(status.uptime);
			console.log(`Daemon running (PID ${status.pid})`);
			console.log(`Socket: ${status.socket}`);
			console.log(`Uptime: ${uptime}`);
			console.log();
			if (status.pools.length === 0) {
				console.log("No active connection pools");
			} else {
				console.log(
					formatTable(
						["Pool", "Active", "Idle", "Queries", "ReadOnly"],
						status.pools.map((p) => [
							p.key,
							String(p.active),
							String(p.idle),
							String(p.queries),
							p.readOnly ? "✓" : "",
						]),
					),
				);
			}
			process.exit(0);
		}

		outputJson(response);
	},
});

function formatUptime(seconds: number): string {
	if (seconds < 60) return `${seconds}s`;
	const mins = Math.floor(seconds / 60);
	const secs = seconds % 60;
	if (mins < 60) return `${mins}m ${secs}s`;
	const hours = Math.floor(mins / 60);
	const remainMins = mins % 60;
	return `${hours}h ${remainMins}m`;
}

export const daemonCommand = defineCommand({
	meta: {
		name: "daemon",
		description: "Manage the pgtool connection daemon",
	},
	subCommands: {
		start: startCommand,
		stop: stopCommand,
		status: statusCommand,
	},
});
