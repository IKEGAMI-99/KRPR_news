#!/usr/bin/env python3
"""Canonicalize Bilibili CDN images to their original-resolution assets."""

from collections.abc import Iterable
import re
import urllib.parse


BILIBILI_IMAGE_HOST_SUFFIXES = ("hdslb.com", "bilivideo.com")

# Bilibili appends image-processing instructions after the original extension,
# for example ``photo.jpg@316w_560h_1e_1c``. The path before ``@`` remains the
# original asset URL. Some variants also append an output extension such as
# ``.webp`` or ``.avif`` after the processing instructions.
_CDN_TRANSFORM_SUFFIX = re.compile(
    r"(?i)(\.(?:avif|gif|jpe?g|png|webp))@[^/?#]*$"
)
_HDSLB_NUMBERED_ALIAS = re.compile(r"^i\d+\.hdslb\.com$", re.I)


def is_bilibili_image_host(host: str | None) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(
        host == suffix or host.endswith("." + suffix)
        for suffix in BILIBILI_IMAGE_HOST_SUFFIXES
    )


def canonicalize_bilibili_image_url(url: str) -> str:
    """Return an original Bilibili CDN URL, leaving unrelated URLs untouched."""

    value = url.strip()
    try:
        parsed = urllib.parse.urlparse(value)
        if not is_bilibili_image_host(parsed.hostname):
            return value

        path = _CDN_TRANSFORM_SUFFIX.sub(r"\1", parsed.path)
        scheme = "https" if parsed.scheme == "http" else parsed.scheme
        # i0/i1/i2 are interchangeable front doors for the same BFS object.
        # Choosing one stable alias prevents the feed and native API copies of
        # an otherwise identical image from appearing as separate gallery items.
        netloc = (
            "i0.hdslb.com"
            if _HDSLB_NUMBERED_ALIAS.fullmatch(parsed.hostname or "")
            else parsed.netloc
        )
        return urllib.parse.urlunparse(parsed._replace(scheme=scheme, netloc=netloc, path=path))
    except Exception:
        return value


def unique_canonical_image_urls(values: Iterable[object], limit: int = 20) -> list[str]:
    """Canonicalize Bilibili variants and retain each original image once."""

    images: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            continue
        url = canonicalize_bilibili_image_url(raw)
        if url in seen:
            continue
        seen.add(url)
        images.append(url)
        if len(images) >= limit:
            break
    return images
