/**
 * WebNav Native Host
 *
 * A minimal relay between the CLI (Unix socket) and Chrome extension (native messaging).
 * Chrome spawns this process when the extension connects via connectNative().
 *
 * Protocol:
 * - Native messaging uses 4-byte length-prefixed JSON on stdin/stdout
 * - Unix socket uses newline-delimited JSON
 */

import { existsSync, mkdirSync, unlinkSync } from "node:fs";
import { type Socket, createServer } from "node:net";
import { homedir, platform } from "node:os";
import { dirname, join } from "node:path";

const IS_WINDOWS = platform() === "win32";

/**
 * Get the IPC path — named pipe on Windows, Unix socket elsewhere.
 */
function getIpcPath(): string {
	if (IS_WINDOWS) return "\\\\.\\pipe\\webnav";
	return join(homedir(), ".webnav", "webnav.sock");
}

const IPC_PATH = getIpcPath();

// Track connected CLI clients
const clients: Set<Socket> = new Set();

// Buffer for reading native messages from stdin
let stdinBuffer = Buffer.alloc(0);

/**
 * Read native message from stdin (4-byte length prefix + JSON)
 */
function readNativeMessage(data: Buffer): Array<unknown> {
	stdinBuffer = Buffer.concat([stdinBuffer, data]);
	const messages: Array<unknown> = [];

	while (stdinBuffer.length >= 4) {
		const length = stdinBuffer.readUInt32LE(0);

		if (stdinBuffer.length < 4 + length) {
			break; // Wait for more data
		}

		const jsonData = stdinBuffer.subarray(4, 4 + length).toString("utf-8");
		stdinBuffer = stdinBuffer.subarray(4 + length);

		try {
			messages.push(JSON.parse(jsonData));
		} catch (e) {
			console.error("[native-host] Failed to parse message:", e);
		}
	}

	return messages;
}

/**
 * Write native message to stdout (4-byte length prefix + JSON)
 */
function writeNativeMessage(message: unknown): void {
	const json = JSON.stringify(message);
	const buffer = Buffer.alloc(4 + json.length);
	buffer.writeUInt32LE(json.length, 0);
	buffer.write(json, 4);
	process.stdout.write(buffer);
}

/**
 * Forward message from extension to all CLI clients
 */
function forwardToClients(message: unknown): void {
	const json = `${JSON.stringify(message)}\n`;
	for (const client of clients) {
		client.write(json);
	}
}

/**
 * Forward message from CLI client to extension
 */
function forwardToExtension(message: unknown): void {
	writeNativeMessage(message);
}

/**
 * Clean up resources on shutdown
 */
function cleanup(server: ReturnType<typeof createServer>): void {
	for (const client of clients) {
		client.destroy();
	}
	clients.clear();
	server.close();
	// Named pipes self-cleanup on Windows; only remove socket file on Unix
	if (!IS_WINDOWS && existsSync(IPC_PATH)) {
		unlinkSync(IPC_PATH);
	}
}

/**
 * Start the native host relay server
 */
export function startNativeHost(): void {
	// On Unix, ensure socket directory exists and remove stale socket
	if (!IS_WINDOWS) {
		const socketDir = dirname(IPC_PATH);
		if (!existsSync(socketDir)) {
			mkdirSync(socketDir, { recursive: true });
		}
		if (existsSync(IPC_PATH)) {
			unlinkSync(IPC_PATH);
		}
	}

	// Create IPC server for CLI clients (Unix socket or Windows named pipe)
	const server = createServer((socket: Socket) => {
		clients.add(socket);

		let buffer = "";

		socket.on("data", (data: Buffer) => {
			buffer += data.toString();
			const lines = buffer.split("\n");
			buffer = lines.pop() || "";

			for (const line of lines) {
				if (line.trim()) {
					try {
						const message = JSON.parse(line);
						forwardToExtension(message);
					} catch (e) {
						console.error("[native-host] Failed to parse client message:", e);
					}
				}
			}
		});

		socket.on("close", () => {
			clients.delete(socket);
		});

		socket.on("error", (err) => {
			console.error("[native-host] Client socket error:", err);
			clients.delete(socket);
		});
	});

	// Handle stdin from Chrome (native messaging)
	process.stdin.on("data", (data: Buffer) => {
		const messages = readNativeMessage(data);
		for (const message of messages) {
			forwardToClients(message);
		}
	});

	process.stdin.on("end", () => {
		// Chrome closed the connection
		cleanup(server);
		process.exit(0);
	});

	server.listen(IPC_PATH, () => {
		// Signal ready by writing to stderr (Chrome ignores stderr)
		console.error(`[native-host] Listening on ${IPC_PATH}`);
	});

	server.on("error", (err) => {
		console.error("[native-host] Server error:", err);
		process.exit(1);
	});

	// Handle process termination
	process.on("SIGINT", () => {
		cleanup(server);
		process.exit(0);
	});

	process.on("SIGTERM", () => {
		cleanup(server);
		process.exit(0);
	});

	process.on("exit", () => {
		cleanup(server);
	});
}
