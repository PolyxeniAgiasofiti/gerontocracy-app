"""Repository availability/freshness checks for the Data Observatory."""

import hashlib
import urllib.error
import urllib.request


SAMPLE_BYTES = 262144


def check_repository_source(url):
    """
    Check one repository URL and return a lightweight source fingerprint.

    This stage verifies availability and basic change signals. It does not yet
    extract/normalise the underlying statistical dataset; that belongs to the
    OSEMN Obtain stage that follows repository approval.
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

            return {
                "status": "SUCCESS",
                "http_status": int(status_code),
                "content_type": content_type,
                "last_modified": last_modified,
                "etag": etag,
                "content_hash": content_hash,
                "notes": (
                    f"Source reachable. Sampled {len(sample)} bytes. "
                    f"Resolved URL: {final_url}"
                ),
            }

    except urllib.error.HTTPError as exc:
        return {
            "status": "FAILED",
            "http_status": int(exc.code),
            "content_type": None,
            "last_modified": None,
            "etag": None,
            "content_hash": None,
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
            "notes": f"Repository check failed: {exc}",
        }
