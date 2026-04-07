/**
 * ADB wrapper class for executing Android Debug Bridge commands.
 */

import { jsonError } from "./output";

export class ADB {
	private _device: string | null = null;

	/**
	 * Run an ADB command and return the result.
	 */
	async run(
		...args: string[]
	): Promise<{ stdout: string; stderr: string; exitCode: number }> {
		const proc = Bun.spawn(["adb", ...args], {
			stdout: "pipe",
			stderr: "pipe",
		});

		const stdout = await new Response(proc.stdout).text();
		const stderr = await new Response(proc.stderr).text();
		const exitCode = await proc.exited;

		return { stdout, stderr, exitCode };
	}

	/**
	 * Run an ADB command, checking for errors.
	 */
	async runChecked(...args: string[]): Promise<string> {
		try {
			const result = await this.run(...args);
			if (result.exitCode !== 0) {
				jsonError(`ADB command failed: ${result.stderr.trim()}`, "ADB_ERROR");
			}
			return result.stdout.trim().replace(/\r/g, "");
		} catch (error) {
			if (error instanceof Error && error.message.includes("ENOENT")) {
				jsonError(
					"ADB not found. Please install Android SDK platform-tools.",
					"ADB_NOT_FOUND",
					"Add platform-tools to your PATH",
				);
			}
			throw error;
		}
	}

	/**
	 * Run an ADB shell command and return stdout.
	 */
	async shell(...args: string[]): Promise<string> {
		return this.runChecked("shell", ...args);
	}

	/**
	 * Run an ADB shell command without checking for errors.
	 */
	async shellUnchecked(
		...args: string[]
	): Promise<{ stdout: string; stderr: string; exitCode: number }> {
		return this.run("shell", ...args);
	}

	/**
	 * Pull a file from the device.
	 */
	async pull(remote: string, local: string): Promise<void> {
		await this.run("pull", remote, local);
	}

	/**
	 * Get connected device ID.
	 */
	async getDevice(): Promise<string> {
		if (this._device !== null) {
			return this._device;
		}

		const result = await this.runChecked("devices");
		const lines = result.split("\n").slice(1); // Skip header

		for (const line of lines) {
			if (line.includes("\tdevice")) {
				this._device = line.split("\t")[0];
				return this._device;
			}
		}

		jsonError(
			"No Android device connected. Run 'adb devices' to check.",
			"NO_DEVICE",
		);
	}

	/**
	 * Get screen dimensions.
	 */
	async getScreenSize(): Promise<{ width: number; height: number }> {
		const output = await this.shell("wm", "size");
		const match = output.match(/(\d+)x(\d+)/);
		if (match) {
			return {
				width: Number.parseInt(match[1], 10),
				height: Number.parseInt(match[2], 10),
			};
		}
		jsonError("Could not determine screen size.", "ADB_ERROR");
	}
}
