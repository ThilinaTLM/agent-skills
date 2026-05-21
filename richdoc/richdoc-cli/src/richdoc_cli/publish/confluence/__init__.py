"""Confluence Cloud publishing pipeline.

Public surface used by the CLI command layer:

- `Creds`, `resolve_creds`           — credential discovery (auth.py)
- `ConfluenceClient`, error classes  — REST client (client.py)
- `html_to_storage`                  — HTML → storage XML (converter.py)
- `publish`, `PublishPlan`, `PublishResult` — orchestration (pipeline.py)
"""

from .auth import CredentialError, Creds, resolve_creds
from .client import (
    Attachment,
    ConfluenceAuthError,
    ConfluenceClient,
    ConfluenceClientError,
    ConfluenceConflictError,
    ConfluenceError,
    ConfluenceNotFoundError,
    ConfluencePermissionError,
    ConfluenceTooLargeError,
    ConfluenceUpstreamError,
    Page,
    Space,
)
from .converter import StorageResult, html_to_storage
from .pipeline import PageOutcome, PublishPlan, PublishResult, publish

__all__ = [
    "Attachment",
    "ConfluenceAuthError",
    "ConfluenceClient",
    "ConfluenceClientError",
    "ConfluenceConflictError",
    "ConfluenceError",
    "ConfluenceNotFoundError",
    "ConfluencePermissionError",
    "ConfluenceTooLargeError",
    "ConfluenceUpstreamError",
    "CredentialError",
    "Creds",
    "Page",
    "PageOutcome",
    "PublishPlan",
    "PublishResult",
    "Space",
    "StorageResult",
    "html_to_storage",
    "publish",
    "resolve_creds",
]
