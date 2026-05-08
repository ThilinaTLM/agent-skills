/**
 * Read local image files into base64 inline-data parts for the Gemini API.
 */

import { readFile } from "node:fs/promises";
import { extname, resolve } from "node:path";

export class InputError extends Error {
	constructor(
		message: string,
		public readonly path: string,
	) {
		super(message);
		this.name = "InputError";
	}
}

const MIME_BY_EXT: Record<string, string> = {
	".png": "image/png",
	".jpg": "image/jpeg",
	".jpeg": "image/jpeg",
	".webp": "image/webp",
	".gif": "image/gif",
};

export interface InputImage {
	absolutePath: string;
	mimeType: string;
	/** Base64-encoded image bytes (no data: URI prefix). */
	data: string;
}

/**
 * Resolve, MIME-detect, read, and base64-encode a single image file.
 * Throws `InputError` on missing/unreadable files or unsupported extensions.
 */
export async function readInputImage(path: string): Promise<InputImage> {
	const absolutePath = resolve(path);
	const ext = extname(absolutePath).toLowerCase();
	const mimeType = MIME_BY_EXT[ext];
	if (!mimeType) {
		throw new InputError(
			`Unsupported image extension '${ext || "(none)"}'. Supported: ${Object.keys(MIME_BY_EXT).join(", ")}`,
			absolutePath,
		);
	}

	let buffer: Buffer;
	try {
		buffer = await readFile(absolutePath);
	} catch (err) {
		const reason = err instanceof Error ? err.message : "unknown error";
		throw new InputError(`Could not read input image: ${reason}`, absolutePath);
	}

	return {
		absolutePath,
		mimeType,
		data: buffer.toString("base64"),
	};
}
