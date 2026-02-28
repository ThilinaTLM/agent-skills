# imagegen

AI image generation plugin for Claude Code using Google Gemini.

## Setup

1. Get a Gemini API key at https://aistudio.google.com/apikey
2. Set the environment variable:
   ```bash
   export GEMINI_API_KEY=your_key_here
   ```
3. Install the plugin:
   ```bash
   /plugin marketplace add /path/to/claude-plugins
   /plugin install imagegen@tlmtech
   ```

## Usage

Ask Claude to generate images naturally:

- "Generate a hero image for the landing page"
- "Create a logo for the project"
- "Make a banner image for the README"

The agent will use the CLI to generate images and place them in your project.

## CLI

```bash
cd imagegen/skills/imagegen/scripts/imagegen-cli && bun install

# Generate an image
bun run dev generate "a blue gradient background" --output ./hero.png

# With options
bun run dev generate "minimalist logo" -o ./logo.png -a 1:1 -s 1024

# Exclude elements
bun run dev gen "landscape painting" -o ./art.png -n "people, text, watermark"
```

## Options

| Flag                    | Description                              |
| ----------------------- | ---------------------------------------- |
| `--output, -o`          | Output file path                         |
| `--aspect-ratio, -a`    | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`      |
| `--size, -s`            | `256`, `512`, `1024` (default)           |
| `--person, -p`          | `dont_allow`, `allow_adult`, `allow_all` |
| `--model, -m`           | Model override                           |
| `--negative-prompt, -n` | What to exclude                          |
