"""Capability matrix for Gemini image-generation models.

Source: https://ai.google.dev/gemini-api/docs/image-generation

Unknown model ids are allowed (the CLI passes them through with a stderr
warning) so that newly released models work without a code change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageModelCapabilities:
    id: str
    aspect_ratios: tuple[str, ...]
    image_sizes: tuple[str, ...] | None  # None == flag not accepted
    thinking_levels: tuple[str, ...] | None  # None == not user-controllable
    max_input_images: int


_ASPECTS_3_1_FLASH: tuple[str, ...] = (
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
)

_ASPECTS_3_PRO_AND_2_5: tuple[str, ...] = (
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
)


DEFAULT_MODEL = "gemini-3.1-flash-image-preview"


IMAGE_MODELS: dict[str, ImageModelCapabilities] = {
    "gemini-3.1-flash-image-preview": ImageModelCapabilities(
        id="gemini-3.1-flash-image-preview",
        aspect_ratios=_ASPECTS_3_1_FLASH,
        image_sizes=("512", "1K", "2K", "4K"),
        thinking_levels=("minimal", "high"),
        max_input_images=14,
    ),
    "gemini-3-pro-image-preview": ImageModelCapabilities(
        id="gemini-3-pro-image-preview",
        aspect_ratios=_ASPECTS_3_PRO_AND_2_5,
        image_sizes=("1K", "2K", "4K"),
        thinking_levels=None,
        max_input_images=14,
    ),
    "gemini-2.5-flash-image": ImageModelCapabilities(
        id="gemini-2.5-flash-image",
        aspect_ratios=_ASPECTS_3_PRO_AND_2_5,
        image_sizes=None,
        thinking_levels=None,
        max_input_images=3,
    ),
}


def get_capabilities(model: str) -> ImageModelCapabilities | None:
    """Look up a model's capability profile, or ``None`` for unknown ids."""
    return IMAGE_MODELS.get(model)
