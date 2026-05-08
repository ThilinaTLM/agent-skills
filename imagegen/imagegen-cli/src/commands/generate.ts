import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { GoogleGenAI } from "@google/genai";
import { defineCommand } from "citty";
import { InputError, type InputImage, readInputImage } from "../lib/inputs.ts";
import { getCapabilities } from "../lib/models.ts";
import { jsonError, jsonOk } from "../lib/output.ts";

const DEFAULT_MODEL = "gemini-3.1-flash-image-preview";

export const generateCommand = defineCommand({
	meta: {
		name: "generate",
		description:
			"Generate or edit an image with Gemini. Pass --image one or more times to edit, restyle, or compose existing images.",
	},
	args: {
		prompt: {
			type: "positional",
			description:
				"Describe the desired image. Provide intent and context; let the model handle creative details.",
			required: true,
		},
		output: {
			type: "string",
			alias: "o",
			description: "Output file path (default: generated_{timestamp}.png)",
		},
		image: {
			type: "string",
			alias: "i",
			description:
				"Input image path (PNG/JPEG/WEBP/GIF). Repeat for multiple references.",
		},
		"aspect-ratio": {
			type: "string",
			alias: "a",
			description: "Aspect ratio (model-validated, e.g. 1:1, 16:9, 21:9)",
		},
		size: {
			type: "string",
			alias: "s",
			description: "Image size: 512, 1K, 2K, 4K (model-dependent)",
		},
		thinking: {
			type: "string",
			alias: "t",
			description:
				"Thinking level: minimal | high. Only honored by gemini-3.1-flash-image-preview.",
		},
		model: {
			type: "string",
			alias: "m",
			description: "Model id (default: gemini-3.1-flash-image-preview)",
			default: DEFAULT_MODEL,
		},
		"negative-prompt": {
			type: "string",
			alias: "n",
			description:
				"Things to exclude. Prefer rewriting the prompt positively when possible.",
		},
	},
	async run({ args }) {
		const apiKey = process.env.GEMINI_API_KEY;
		if (!apiKey) {
			jsonError(
				"GEMINI_API_KEY environment variable is not set",
				"API_KEY_MISSING",
				"Get your API key at https://aistudio.google.com/apikey and set it: export GEMINI_API_KEY=your_key",
			);
		}

		const prompt = args.prompt;
		const aspectRatio = args["aspect-ratio"] || "";
		const size = args.size || "";
		const thinking = (args.thinking || "").toLowerCase();
		const model = args.model || DEFAULT_MODEL;
		const negativePrompt = args["negative-prompt"] || "";

		// citty yields an array when a flag repeats; coerce to string[].
		const rawImage = args.image as string | string[] | undefined;
		const imagePaths: string[] = rawImage
			? Array.isArray(rawImage)
				? rawImage
				: [rawImage]
			: [];

		// --- Capability-driven validation -----------------------------------
		const caps = getCapabilities(model);
		if (!caps) {
			console.error(
				`[imagegen] Warning: unknown model '${model}'. Skipping capability validation; the API may reject the call.`,
			);
		}

		if (caps && aspectRatio && !caps.aspectRatios.includes(aspectRatio)) {
			jsonError(
				`Invalid aspect ratio '${aspectRatio}' for model '${model}'. Valid: ${caps.aspectRatios.join(", ")}`,
				"INVALID_PARAMS",
			);
		}

		if (caps && size) {
			if (caps.imageSizes === null) {
				jsonError(
					`Model '${model}' does not accept --size. Omit the flag or switch to a model that supports it (e.g. gemini-3.1-flash-image-preview).`,
					"INVALID_PARAMS",
				);
			} else if (!caps.imageSizes.includes(size)) {
				jsonError(
					`Invalid size '${size}' for model '${model}'. Valid: ${caps.imageSizes.join(", ")}`,
					"INVALID_PARAMS",
				);
			}
		}

		if (caps && thinking) {
			if (caps.thinkingLevels === null) {
				jsonError(
					`Model '${model}' does not accept --thinking. Omit the flag or use gemini-3.1-flash-image-preview.`,
					"INVALID_PARAMS",
				);
			} else if (!caps.thinkingLevels.includes(thinking)) {
				jsonError(
					`Invalid thinking level '${thinking}' for model '${model}'. Valid: ${caps.thinkingLevels.join(", ")}`,
					"INVALID_PARAMS",
				);
			}
		}

		if (caps && imagePaths.length > caps.maxInputImages) {
			jsonError(
				`Too many input images (${imagePaths.length}) for model '${model}'. Max: ${caps.maxInputImages}.`,
				"INVALID_PARAMS",
			);
		}

		// --- Load input images ----------------------------------------------
		let inputImages: InputImage[] = [];
		try {
			inputImages = await Promise.all(imagePaths.map(readInputImage));
		} catch (err) {
			if (err instanceof InputError) {
				jsonError(`${err.message} (${err.path})`, "INPUT_ERROR");
			}
			throw err;
		}

		// --- Build request --------------------------------------------------
		const fullPrompt = negativePrompt
			? `${prompt}. Do not include: ${negativePrompt}.`
			: prompt;

		const parts: Array<
			{ text: string } | { inlineData: { mimeType: string; data: string } }
		> = [{ text: fullPrompt }];
		for (const img of inputImages) {
			parts.push({ inlineData: { mimeType: img.mimeType, data: img.data } });
		}

		const imageConfig: Record<string, string> = {};
		if (aspectRatio) imageConfig.aspectRatio = aspectRatio;
		if (size) imageConfig.imageSize = size;

		const config: Record<string, unknown> = {
			responseModalities: ["IMAGE"],
		};
		if (Object.keys(imageConfig).length > 0) {
			config.imageConfig = imageConfig;
		}
		if (thinking) {
			// SDK enum is upper-case (MINIMAL | HIGH). Normalize.
			config.thinkingConfig = { thinkingLevel: thinking.toUpperCase() };
		}

		const outputPath = resolve(args.output || `generated_${Date.now()}.png`);

		// --- Call API -------------------------------------------------------
		try {
			const ai = new GoogleGenAI({ apiKey });
			const response = await ai.models.generateContent({
				model,
				contents: [{ role: "user", parts }],
				config,
			});

			const responseParts = response.candidates?.[0]?.content?.parts;
			if (!responseParts || responseParts.length === 0) {
				jsonError("No content in API response", "API_ERROR");
			}

			// Pick the final image: prefer the last non-thought image part;
			// fall back to the last image part if all are thoughts.
			const imageParts = responseParts.filter((p) =>
				p.inlineData?.mimeType?.startsWith("image/"),
			);
			if (imageParts.length === 0) {
				jsonError("API response did not contain an image", "API_ERROR");
			}
			const nonThought = imageParts.filter((p) => !p.thought);
			const finalPart = (nonThought.length > 0 ? nonThought : imageParts).at(
				-1,
			);
			const inline = finalPart?.inlineData;
			if (!inline?.data || !inline.mimeType) {
				jsonError("Image data missing from API response", "API_ERROR");
			}

			const buffer = Buffer.from(inline.data, "base64");
			try {
				await mkdir(dirname(outputPath), { recursive: true });
				await writeFile(outputPath, buffer);
			} catch (err) {
				const reason = err instanceof Error ? err.message : "unknown error";
				jsonError(`Could not write output file: ${reason}`, "OUTPUT_ERROR");
			}

			const result: Record<string, unknown> = {
				file: outputPath,
				mimeType: inline.mimeType,
				size: buffer.length,
				prompt,
				model,
			};
			if (aspectRatio) result.aspectRatio = aspectRatio;
			if (size) result.imageSize = size;
			if (thinking) result.thinkingLevel = thinking;
			if (inputImages.length > 0) {
				result.inputImages = inputImages.map((i) => i.absolutePath);
			}
			jsonOk(result);
		} catch (err) {
			const message = err instanceof Error ? err.message : "Unknown API error";
			jsonError(message, "API_ERROR");
		}
	},
});
