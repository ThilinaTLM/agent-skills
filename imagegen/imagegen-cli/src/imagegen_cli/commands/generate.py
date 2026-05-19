"""``imagegen generate`` — text-to-image and image-editing via Google Gemini."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import click

from ..api_key import resolve_api_key
from ..inputs import InputError, InputImage, read_input_image
from ..models import DEFAULT_MODEL, get_capabilities
from ..output import json_error, json_ok

_API_KEY_MISSING_HINT = (
    "Set GEMINI_API_KEY env var, or write the key to '.gemini-key' in the "
    "project root (gitignore it) or '~/.gemini-key' for machine-wide use. "
    "Get a key at https://aistudio.google.com/apikey."
)


@click.command(
    "generate",
    short_help="Generate or edit an image with Gemini.",
    help=(
        "Generate or edit an image with Gemini. Pass --image one or more times "
        "to edit, restyle, or compose existing images."
    ),
)
@click.argument("prompt")
@click.option(
    "-o",
    "--output",
    "output",
    default=None,
    help="Output file path (default: generated_{timestamp}.png)",
)
@click.option(
    "-i",
    "--image",
    "image_paths",
    multiple=True,
    help="Input image path (PNG/JPEG/WEBP/GIF). Repeat for multiple references.",
)
@click.option(
    "-a",
    "--aspect-ratio",
    "aspect_ratio",
    default="",
    help="Aspect ratio (model-validated, e.g. 1:1, 16:9, 21:9).",
)
@click.option(
    "-s",
    "--size",
    "size",
    default="",
    help="Image size: 512, 1K, 2K, 4K (model-dependent).",
)
@click.option(
    "-t",
    "--thinking",
    "thinking",
    default="",
    help="Thinking level: minimal | high. Only honored by gemini-3.1-flash-image-preview.",
)
@click.option(
    "-m",
    "--model",
    "model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Model id.",
)
@click.option(
    "-n",
    "--negative-prompt",
    "negative_prompt",
    default="",
    help="Things to exclude. Prefer rewriting the prompt positively when possible.",
)
def cmd(
    prompt: str,
    output: str | None,
    image_paths: tuple[str, ...],
    aspect_ratio: str,
    size: str,
    thinking: str,
    model: str,
    negative_prompt: str,
) -> None:
    # --- API key --------------------------------------------------------
    resolved = resolve_api_key()
    if resolved is None:
        json_error(
            "Gemini API key not found",
            code="API_KEY_MISSING",
            hint=_API_KEY_MISSING_HINT,
        )

    # Normalize.
    thinking = thinking.lower()

    # --- Capability-driven validation -----------------------------------
    caps = get_capabilities(model)
    if caps is None:
        # Match the TS warning verbatim; goes to stderr so stdout stays clean.
        print(
            f"[imagegen] Warning: unknown model '{model}'. "
            "Skipping capability validation; the API may reject the call.",
            file=sys.stderr,
        )

    if caps is not None and aspect_ratio and aspect_ratio not in caps.aspect_ratios:
        json_error(
            f"Invalid aspect ratio '{aspect_ratio}' for model '{model}'. "
            f"Valid: {', '.join(caps.aspect_ratios)}",
            code="INVALID_PARAMS",
        )

    if caps is not None and size:
        if caps.image_sizes is None:
            json_error(
                f"Model '{model}' does not accept --size. Omit the flag or "
                "switch to a model that supports it "
                "(e.g. gemini-3.1-flash-image-preview).",
                code="INVALID_PARAMS",
            )
        elif size not in caps.image_sizes:
            json_error(
                f"Invalid size '{size}' for model '{model}'. "
                f"Valid: {', '.join(caps.image_sizes)}",
                code="INVALID_PARAMS",
            )

    if caps is not None and thinking:
        if caps.thinking_levels is None:
            json_error(
                f"Model '{model}' does not accept --thinking. Omit the flag "
                "or use gemini-3.1-flash-image-preview.",
                code="INVALID_PARAMS",
            )
        elif thinking not in caps.thinking_levels:
            json_error(
                f"Invalid thinking level '{thinking}' for model '{model}'. "
                f"Valid: {', '.join(caps.thinking_levels)}",
                code="INVALID_PARAMS",
            )

    if caps is not None and len(image_paths) > caps.max_input_images:
        json_error(
            f"Too many input images ({len(image_paths)}) for model "
            f"'{model}'. Max: {caps.max_input_images}.",
            code="INVALID_PARAMS",
        )

    # --- Load input images ----------------------------------------------
    input_images: list[InputImage] = []
    try:
        for raw_path in image_paths:
            input_images.append(read_input_image(raw_path))
    except InputError as err:
        json_error(f"{err.message} ({err.path})", code="INPUT_ERROR")

    # --- Build request --------------------------------------------------
    # Import the SDK lazily so capability/input errors don't pay the import cost.
    from google import genai
    from google.genai import types

    full_prompt = (
        f"{prompt}. Do not include: {negative_prompt}." if negative_prompt else prompt
    )

    parts: list[types.Part] = [types.Part(text=full_prompt)]
    for img in input_images:
        parts.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type=img.mime_type,
                    data=img.data_bytes,
                )
            )
        )

    config_kwargs: dict[str, Any] = {"response_modalities": ["IMAGE"]}
    image_config_kwargs: dict[str, Any] = {}
    if aspect_ratio:
        image_config_kwargs["aspect_ratio"] = aspect_ratio
    if size:
        image_config_kwargs["image_size"] = size
    if image_config_kwargs:
        config_kwargs["image_config"] = types.ImageConfig(**image_config_kwargs)
    if thinking:
        # SDK enum is upper-case (MINIMAL | HIGH). Normalize on the way out.
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=thinking.upper()
        )
    config = types.GenerateContentConfig(**config_kwargs)

    if output:
        output_path = Path(output).resolve()
    else:
        # Date.now() in TS gives ms; preserve millisecond precision.
        output_path = (Path.cwd() / f"generated_{int(time.time() * 1000)}.png").resolve()

    # --- Call API -------------------------------------------------------
    try:
        client = genai.Client(api_key=resolved.key)
        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=parts)],
            config=config,
        )

        response_parts = None
        if response.candidates and response.candidates[0].content:
            response_parts = response.candidates[0].content.parts
        if not response_parts:
            json_error("No content in API response", code="API_ERROR")

        image_parts = [
            p
            for p in response_parts
            if p.inline_data
            and p.inline_data.mime_type
            and p.inline_data.mime_type.startswith("image/")
        ]
        if not image_parts:
            json_error("API response did not contain an image", code="API_ERROR")

        non_thought = [p for p in image_parts if not getattr(p, "thought", False)]
        final = (non_thought or image_parts)[-1]
        blob = final.inline_data
        if not blob or not blob.data or not blob.mime_type:
            json_error("Image data missing from API response", code="API_ERROR")

        # SDK returns raw bytes for inline_data.data; tolerate the rare base64
        # string shape some versions have produced.
        raw = blob.data
        if isinstance(raw, str):
            import base64

            data_bytes = base64.b64decode(raw)
        else:
            data_bytes = raw

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(data_bytes)
        except OSError as exc:
            json_error(
                f"Could not write output file: {exc}", code="OUTPUT_ERROR"
            )

        result: dict[str, Any] = {
            "file": str(output_path),
            "mimeType": blob.mime_type,
            "size": len(data_bytes),
            "prompt": prompt,
            "model": model,
        }
        if aspect_ratio:
            result["aspectRatio"] = aspect_ratio
        if size:
            result["imageSize"] = size
        if thinking:
            result["thinkingLevel"] = thinking
        if input_images:
            result["inputImages"] = [str(i.absolute_path) for i in input_images]
        json_ok(**result)
    except SystemExit:
        # Re-raise json_ok / json_error sentinels so they aren't swallowed.
        raise
    except Exception as exc:  # noqa: BLE001 — match TS: fold every API failure under API_ERROR
        message = str(exc) or "Unknown API error"
        json_error(message, code="API_ERROR")
