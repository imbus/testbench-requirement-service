import base64
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
    from jira.resilientsession import ResilientSession
    from jira.resources import Issue
except ImportError:  # pragma: no cover
    pass
from sanic.log import logger

MAX_EMBEDDED_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB limit for embedded images
JIRA_ATTACHMENT_URL_PATTERN = re.compile(r"^/rest/api/\d+/attachment/content/(\d+)$")
DEFAULT_INLINE_STYLES_PATH = Path(__file__).parents[2] / "static" / "rendered_fields.css"

default_inline_styles = ""


def load_inline_styles(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.debug(f"Inline style file not found at {path}; continuing without styles")
        return ""
    except OSError as exc:  # pragma: no cover - edge case
        logger.warning(f"Failed to read inline styles from {path}: {exc}")
        return ""


def build_rendered_field_html(
    issue: Issue,
    field_id: str,
    jira_server_url: str,
    *,
    include_head: bool = True,
) -> str:
    """Build HTML for a Jira rendered field."""
    rendered_html = getattr(issue.renderedFields, field_id, "")
    if not rendered_html:
        return wrap_in_html("", include_head=include_head)

    enriched_body = enrich_rendered_html(
        rendered_html,
        issue=issue,
        jira_server_url=jira_server_url,
    )
    return wrap_in_html(enriched_body, include_head=include_head)


def wrap_in_html(body: str, include_head: bool = True) -> str:
    if include_head:
        styles = default_inline_styles or load_inline_styles(DEFAULT_INLINE_STYLES_PATH)
        style_tag = f"<style>{styles}</style>" if styles else ""
        head = f"<head>{style_tag}</head>"
    else:
        head = ""
    return f"<html>{head}<body>{body}</body></html>"


def enrich_rendered_html(
    rendered_html: str,
    issue: Issue,
    jira_server_url: str,
) -> str:
    """Normalize Jira rendered HTML for downstream consumers."""
    if not rendered_html:
        return ""
    soup = BeautifulSoup(rendered_html, "html.parser")
    process_image_tags(soup, issue, jira_server_url)
    process_anchor_tags(soup, jira_server_url)
    return str(soup)


def build_attachment_catalog(issue: Issue) -> dict[str, dict[str, Any]]:
    attachments = getattr(issue.fields, "attachment", []) or []
    catalog: dict[str, dict[str, Any]] = {}
    for attachment in attachments:
        attachment_id = getattr(attachment, "id", None)
        if not attachment_id:
            continue

        mime_type = getattr(attachment, "mimeType", None)
        if not mime_type:
            logger.warning(f"Attachment {attachment_id} missing mimeType metadata")
            continue

        entry: dict[str, Any] = {
            "mime_type": mime_type,
            "content_url": getattr(attachment, "content", ""),
            "encoded": None,
        }

        if mime_type.startswith("image/"):
            size = getattr(attachment, "size", None)
            if size and size > MAX_EMBEDDED_IMAGE_SIZE:
                logger.warning(
                    f"Attachment {attachment_id} size ({size} bytes) exceeds "
                    f"maximum allowed size ({MAX_EMBEDDED_IMAGE_SIZE} bytes)"
                )
                catalog[attachment_id] = entry
                continue

            try:
                image_bytes = attachment.get()
            except Exception as e:
                logger.debug(f"Could not fetch attachment {attachment_id}: {e}")
                catalog[attachment_id] = entry
                continue

            if len(image_bytes) > MAX_EMBEDDED_IMAGE_SIZE:
                logger.warning(
                    f"Attachment {attachment_id} size ({len(image_bytes)} bytes) exceeds "
                    f"maximum allowed size ({MAX_EMBEDDED_IMAGE_SIZE} bytes)"
                )
            else:
                entry["encoded"] = base64.b64encode(image_bytes).decode("utf-8")
                logger.debug(
                    f"Successfully processed attachment {attachment_id} ({len(image_bytes)} bytes)"
                )

        catalog[attachment_id] = entry
    return catalog


def process_image_tags(
    soup: BeautifulSoup,
    issue: Issue,
    jira_server_url: str,
) -> None:
    attachment_catalog = build_attachment_catalog(issue)
    image_cache: dict[str, str | None] = {}

    for img in soup.find_all("img"):
        src = str(img.get("src", "")).strip()

        if not src:
            img.decompose()
            continue

        if src.startswith("data:"):
            continue

        if src.startswith("cid:"):
            img.attrs.pop("src", None)
            continue

        if handle_attachment_image(img, src, attachment_catalog, jira_server_url):
            continue

        if handle_remote_image(img, src, image_cache, issue, jira_server_url):
            continue

        # Unsupported
        logger.warning(f"Removed image with unsupported src: {src}")
        img.attrs.pop("src", None)


def handle_attachment_image(
    img, src: str, attachment_catalog: dict[str, dict[str, Any]], jira_server_url: str
) -> bool:
    attachment_match = JIRA_ATTACHMENT_URL_PATTERN.fullmatch(src)
    if attachment_match:
        apply_attachment_image(
            img,
            attachment_catalog,
            attachment_match.group(1),
            jira_server_url,
        )
        return True
    return False


def apply_attachment_image(
    img,
    attachment_catalog: dict[str, dict[str, Any]],
    attachment_id: str,
    jira_server_url: str,
) -> None:
    attachment_info = attachment_catalog.get(attachment_id)
    if not attachment_info:
        img.attrs.pop("src", None)
        logger.warning(f"Attachment {attachment_id} not found in validated attachments")
        return

    encoded = attachment_info.get("encoded")
    mime_type = attachment_info.get("mime_type") or "image/png"
    if encoded:
        img["src"] = f"data:{mime_type};base64,{encoded}"
        return

    fallback_url = attachment_info.get("content_url") or f"/attachment/{attachment_id}"
    img["src"] = build_absolute_jira_url(fallback_url, jira_server_url)


def handle_remote_image(
    img, src: str, image_cache: dict[str, str | None], issue: Issue, jira_server_url: str
) -> bool:
    # Normalize relative URLs
    if is_relative_url(src):
        src = build_absolute_jira_url(src, jira_server_url)

    if not is_remote_http(src):
        return False

    # Check cache
    if src in image_cache:
        if image_cache[src]:
            img["src"] = image_cache[src]
        return True

    # Try to inline
    if should_inline_remote_image(src):
        data_uri = fetch_image_as_data_uri(issue, src)
        image_cache[src] = data_uri
        if data_uri:
            img["src"] = data_uri
            return True

    # Use remote URL directly
    image_cache[src] = None
    img["src"] = src
    return True


def process_anchor_tags(soup: BeautifulSoup, jira_server_url: str) -> None:
    for anchor in soup.find_all("a"):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("http://", "https://", "mailto:")):
            continue
        if href.startswith("#"):
            continue
        if is_relative_url(href):
            anchor["href"] = build_absolute_jira_url(href, jira_server_url)


def build_absolute_jira_url(url: str, jira_server_url: str) -> str:
    """Convert relative Jira URL to absolute using base server URL."""
    if not url:
        return url
    if url.startswith(("http://", "https://")):
        return url
    base = jira_server_url if jira_server_url.endswith("/") else f"{jira_server_url}/"
    relative = url.lstrip("/")
    return urljoin(base, relative)


def is_relative_url(value: str) -> bool:
    if value.startswith(("data:", "mailto:", "cid:", "#")):
        return False
    parsed = urlparse(value)
    return parsed.scheme == ""


def is_remote_http(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def should_inline_remote_image(src: str) -> bool:
    return True  # For now, inline all remote images


def fetch_image_as_data_uri(
    issue: Issue,
    url: str,
) -> str | None:
    session: ResilientSession | None = getattr(issue, "_session", None)
    if session is None:
        return None

    try:
        response = session.get(url)
        response.raise_for_status()
    except Exception as e:
        logger.debug(f"Failed to inline image from {url}: {e}")
        return None

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        return None

    content = response.content
    if len(content) > MAX_EMBEDDED_IMAGE_SIZE:
        logger.debug("Image exceeds max embed size; skipping inline encoding")
        return None

    encoded = base64.b64encode(content).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"
