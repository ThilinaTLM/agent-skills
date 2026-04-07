import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { GoogleGenAI } from "@google/genai";
import { defineCommand } from "citty";
import { jsonError, jsonOk } from "../lib/output";

const VALID_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"];
const VALID_SIZES = ["256", "512", "1024"];
const VALID_PERSON_MODES = ["dont_allow", "allow_adult", "allow_all"];

export const generateCommand = defineCommand({
	meta: {
		name: "generate",
		description: "Generate an image from a text prompt",
	},
	args: {
		prompt: {
			type: "positional",
			description: "Text description of the image to generate",
			required: true,
		},
		output: {
			type: "string",
			alias: "o",
			description: "Output file path (default: generated_{timestamp}.png)",
		},
		"aspect-ratio": {
			type: "string",
			alias: "a",
			description: "Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4",
		},
		size: {
			type: "string",
			alias: "s",
			description: "Image size: 256, 512, 1024",
			default: "1024",
		},
		person: {
			type: "string",
			alias: "p",
			description: "Person generation: dont_allow, allow_adult, allow_all",
		},
		model: {
			type: "string",
			alias: "m",
			description: "Model to use",
			default: "gemini-3.1-flash-image-preview",
		},
		"negative-prompt": {
			type: "string",
			alias: "n",
			description: "What to exclude from the image",
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
			return;
		}

		const prompt = args.prompt;
		const aspectRatio = args["aspect-ratio"] || "";
		const size = args.size || "1024";
		const person = args.person || "";
		const model = args.model || "gemini-3.1-flash-image-preview";
		const negativePrompt = args["negative-prompt"] || "";

		// Validate aspect ratio
		if (aspectRatio && !VALID_ASPECT_RATIOS.includes(aspectRatio)) {
			jsonError(
				`Invalid aspect ratio: ${aspectRatio}. Valid values: ${VALID_ASPECT_RATIOS.join(", ")}`,
				"INVALID_PARAMS",
			);
			return;
		}

		// Validate size
		if (!VALID_SIZES.includes(size)) {
			jsonError(
				`Invalid size: ${size}. Valid values: ${VALID_SIZES.join(", ")}`,
				"INVALID_PARAMS",
			);
			return;
		}

		// Validate person mode
		if (person && !VALID_PERSON_MODES.includes(person)) {
			jsonError(
				`Invalid person mode: ${person}. Valid values: ${VALID_PERSON_MODES.join(", ")}`,
				"INVALID_PARAMS",
			);
			return;
		}

		// Resolve output path
		const outputPath = resolve(args.output || `generated_${Date.now()}.png`);

		// Build the full prompt
		const fullPrompt = negativePrompt
			? `${prompt}. Avoid: ${negativePrompt}`
			: prompt;

		// Call Gemini API
		try {
			const ai = new GoogleGenAI({ apiKey });

			const imageConfig: Record<string, string> = {};
			if (aspectRatio) imageConfig.aspectRatio = aspectRatio;
			if (size) imageConfig.imageSize = size;
			if (person) imageConfig.personGeneration = person;

			const response = await ai.models.generateContent({
				model,
				contents: [{ role: "user", parts: [{ text: fullPrompt }] }],
				config: {
					responseModalities: ["IMAGE"],
					...(Object.keys(imageConfig).length > 0 && {
						imageConfig,
					}),
				},
			});

			// Extract image data from response
			const parts = response.candidates?.[0]?.content?.parts;
			if (!parts || parts.length === 0) {
				jsonError("No image data in API response", "API_ERROR");
				return;
			}

			const imagePart = parts.find((part) =>
				part.inlineData?.mimeType?.startsWith("image/"),
			);
			if (!imagePart?.inlineData) {
				jsonError("API response did not contain an image", "API_ERROR");
				return;
			}

			const { data, mimeType } = imagePart.inlineData;
			if (!data || !mimeType) {
				jsonError("Image data is missing from response", "API_ERROR");
				return;
			}

			// Decode and write
			const buffer = Buffer.from(data, "base64");

			await mkdir(dirname(outputPath), { recursive: true });
			await writeFile(outputPath, buffer);

			jsonOk({
				file: outputPath,
				mimeType,
				size: buffer.length,
				prompt,
			});
		} catch (err) {
			const message = err instanceof Error ? err.message : "Unknown API error";
			jsonError(message, "API_ERROR");
		}
	},
});
