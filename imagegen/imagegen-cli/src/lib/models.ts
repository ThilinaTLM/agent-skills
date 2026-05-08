/**
 * Capability matrix for Gemini image-generation models.
 *
 * Source: https://ai.google.dev/gemini-api/docs/image-generation
 *
 * Unknown model ids are allowed (the CLI passes them through with a stderr
 * warning) so that newly released models work without a code change.
 */

export interface ImageModelCapabilities {
	id: string;
	/** Allowed `aspectRatio` values. */
	aspectRatios: string[];
	/** Allowed `imageSize` values, or null when the model does not accept the field. */
	imageSizes: string[] | null;
	/** Allowed `thinkingLevel` values (lower-case), or null when not user-controllable. */
	thinkingLevels: string[] | null;
	/** Maximum number of input/reference images supported in a single call. */
	maxInputImages: number;
}

const ASPECTS_3_1_FLASH = [
	"1:1",
	"1:4",
	"1:8",
	"2:3",
	"3:2",
	"3:4",
	"4:1",
	"4:3",
	"4:5",
	"5:4",
	"8:1",
	"9:16",
	"16:9",
	"21:9",
];

const ASPECTS_3_PRO_AND_2_5 = [
	"1:1",
	"2:3",
	"3:2",
	"3:4",
	"4:3",
	"4:5",
	"5:4",
	"9:16",
	"16:9",
	"21:9",
];

export const IMAGE_MODELS: Record<string, ImageModelCapabilities> = {
	"gemini-3.1-flash-image-preview": {
		id: "gemini-3.1-flash-image-preview",
		aspectRatios: ASPECTS_3_1_FLASH,
		imageSizes: ["512", "1K", "2K", "4K"],
		thinkingLevels: ["minimal", "high"],
		maxInputImages: 14,
	},
	"gemini-3-pro-image-preview": {
		id: "gemini-3-pro-image-preview",
		aspectRatios: ASPECTS_3_PRO_AND_2_5,
		imageSizes: ["1K", "2K", "4K"],
		thinkingLevels: null,
		maxInputImages: 14,
	},
	"gemini-2.5-flash-image": {
		id: "gemini-2.5-flash-image",
		aspectRatios: ASPECTS_3_PRO_AND_2_5,
		imageSizes: null,
		thinkingLevels: null,
		maxInputImages: 3,
	},
};

/**
 * Look up a model's capability profile.
 *
 * Returns `null` for unknown ids; callers should warn and skip validation.
 */
export function getCapabilities(model: string): ImageModelCapabilities | null {
	return IMAGE_MODELS[model] ?? null;
}
