---
name: imagegen
description: This skill should be used when the user asks to "generate an image", "create a cover image", "make an illustration", "generate artwork", "create a hero image", "generate a logo", "make a banner", "create an image for", "generate a thumbnail", "make an icon", "create visual content", or needs AI-generated images for their project. Provides a CLI with JSON output optimized for LLM consumption.
---

# ImageGen

AI image generation tool with **JSON output** for LLM-friendly automation. Uses Google Gemini to generate images from text prompts.

## CLI Discovery

The CLI is located at `./scripts/imagegen-cli/` relative to this SKILL.md file.

| Platform         | Script     |
| ---------------- | ---------- |
| Unix/Linux/macOS | `imagegen` |

**Claude Code:** Use `${CLAUDE_PLUGIN_ROOT}/skills/imagegen/scripts/imagegen-cli/imagegen`

## Prerequisites

- Bun runtime (https://bun.sh)
- `GEMINI_API_KEY` environment variable set with a valid Google AI Studio API key

If the API key is not set, instruct the user to:

1. Get a key at https://aistudio.google.com/apikey
2. Add `export GEMINI_API_KEY=your_key` to their shell profile (`~/.bashrc` or `~/.zshrc`)
3. Restart their terminal or run `source ~/.bashrc`

## Important Rules

- **Always use `--output`** to place generated images in the project's assets directory (e.g. `src/assets/`, `public/images/`)
- **Verify the generated image** by reading it with the Read tool after generation
- **Use descriptive filenames** that match the image content (e.g. `hero-banner.png`, `logo-dark.png`)
- **Never generate images** with copyrighted characters, real people's likenesses, or harmful content

## Commands

### generate (alias: gen)

Generate an image from a text prompt.

```bash
imagegen generate "a minimalist blue gradient background" --output ./src/assets/hero-bg.png
imagegen gen "modern tech company logo, flat design" -o ./public/logo.png
```

**Arguments:**

| Arg                     | Flag                  | Description                                                           |
| ----------------------- | --------------------- | --------------------------------------------------------------------- |
| `prompt`                | positional (required) | Text description of the image                                         |
| `--output, -o`          | string                | Output file path (default: `generated_{timestamp}.png`)               |
| `--aspect-ratio, -a`    | string                | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`                                   |
| `--size, -s`            | string                | `256`, `512`, `1024` (default: `1024`)                                |
| `--person, -p`          | string                | `dont_allow`, `allow_adult`, `allow_all`                              |
| `--model, -m`           | string                | Model override (default: `gemini-2.0-flash-preview-image-generation`) |
| `--negative-prompt, -n` | string                | What to exclude from the image                                        |

**Success response:**

```json
{
  "ok": true,
  "file": "/absolute/path/to/image.png",
  "mimeType": "image/png",
  "size": 245760,
  "prompt": "a minimalist blue gradient background"
}
```

**Error responses:**

```json
{
  "ok": false,
  "error": "GEMINI_API_KEY environment variable is not set",
  "code": "API_KEY_MISSING",
  "hint": "Get your API key at https://aistudio.google.com/apikey and set it: export GEMINI_API_KEY=your_key"
}
```

```json
{
  "ok": false,
  "error": "Invalid aspect ratio: 2:1. Valid values: 1:1, 16:9, 9:16, 4:3, 3:4",
  "code": "INVALID_PARAMS"
}
```

```json
{
  "ok": false,
  "error": "API response did not contain an image",
  "code": "API_ERROR"
}
```

## Workflows

### Hero Image for Website

```bash
imagegen generate "modern abstract gradient background, purple and blue tones, subtle geometric shapes, professional" \
  --output ./src/assets/hero-bg.png \
  --aspect-ratio 16:9 \
  --size 1024
```

### Logo Variations

```bash
imagegen gen "minimalist tech startup logo, letter M, flat design, white background" \
  -o ./public/images/logo-light.png -a 1:1 -s 1024

imagegen gen "minimalist tech startup logo, letter M, flat design, dark background" \
  -o ./public/images/logo-dark.png -a 1:1 -s 1024
```

### Iterative Refinement with Negative Prompts

```bash
imagegen generate "watercolor landscape, rolling hills, sunset" \
  --output ./assets/landscape.png \
  --negative-prompt "people, buildings, text, watermark"
```

### Social Media Banner

```bash
imagegen gen "abstract tech conference banner, neon accents, dark theme" \
  -o ./public/og-image.png -a 16:9
```

## Error Handling

All errors return JSON with `"ok":false`:

| Code              | Meaning                          |
| ----------------- | -------------------------------- |
| `API_KEY_MISSING` | `GEMINI_API_KEY` env var not set |
| `API_ERROR`       | Gemini API call failed           |
| `INVALID_PARAMS`  | Bad argument value               |
| `OUTPUT_ERROR`    | Could not write output file      |
| `PREREQ_MISSING`  | Bun runtime not found            |
