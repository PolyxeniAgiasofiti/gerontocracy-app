"""Repository availability checks for the Data Observatory."""

import hashlib
import urllib.error
import urllib.request


SAMPLE_BYTES = 262144


def check_repository_source(url):
    """
    Check whether a repository URL is reachable.

    Important:
    - HTML landing pages are treated as availability checks only.
      Their page content can change dynamically, so we do not use their
      HTML body as a reliable dataset-change fingerprint.
    - For non-HTML resources, a lightweight fingerprint is created from
      stable headers and a content sample. Actual dataset versioning and
      snapshot comparison belongs to Stage 3 (OSEMN Obtain).
    """

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 Gerontocracy-Data-Observatory/1.0"
            ),
            "Accept": "text/html,application/json,text/csv,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:
            sample = response.read(SAMPLE_BYTES)
            status_code = getattr(response, "status", None) or 200
            headers = response.headers
            final_url = response.geturl()

            content_type = headers.get("Content-Type")
            last_modified = headers.get("Last-Modified")
            etag = headers.get("ETag")

            content_type_lower = (
                content_type or ""
            ).lower()

            # HTML repository pages are often dynamic. Hashing the page body
            # creates false "Changed=True" signals even when the underlying
            # statistical data have not changed.
            if "text/html" in content_type_lower:
                content_hash = None
                change_detection_supported = False
                notes = (
                    "Repository landing page reachable. "
                    "HTML content is treated as an availability check only; "
                    "dataset change detection is deferred to Stage 3 "
                    "(data-object snapshots). "
                    f"Resolved URL: {final_url}"
                )

            else:
                fingerprint_source = "|".join(
                    [
                        final_url or "",
                        str(status_code),
                        content_type or "",
                        last_modified or "",
                        etag or "",
                    ]
                ).encode("utf-8") + sample

                content_hash = hashlib.sha256(
                    fingerprint_source
                ).hexdigest()

                change_detection_supported = True
                notes = (
                    f"Source reachable. Sampled {len(sample)} bytes. "
                    "A lightweight non-HTML fingerprint was created. "
                    f"Resolved URL: {final_url}"
                )

            return {
                "status": "SUCCESS",
                "http_status": int(status_code),
                "content_type": content_type,
                "last_modified": last_modified,
                "etag": etag,
                "content_hash": content_hash,
                "change_detection_supported": (
                    change_detection_supported
                ),
                "notes": notes,
            }

    except urllib.error.HTTPError as exc:
        return {
            "status": "FAILED",
            "http_status": int(exc.code),
            "content_type": None,
            "last_modified": None,
            "etag": None,
            "content_hash": None,
            "change_detection_supported": False,
            "notes": f"HTTP error: {exc.code} {exc.reason}",
        }

    except Exception as exc:
        return {
            "status": "FAILED",
            "http_status": None,
            "content_type": None,
            "last_modified": None,
            "etag": None,
            "content_hash": None,
            "change_detection_supported": False,
            "notes": f"Repository check failed: {exc}",
        }
