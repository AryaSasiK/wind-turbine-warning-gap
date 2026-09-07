"""HTTP range-request reader for remote zip archives (Zenodo).

Lets us pull a handful of small members out of a ~1.4 GB zip without ever
downloading the whole archive. Used to build the Hill of Towie alarm-code
inventory from the open Zenodo record on a machine with no spare disk.

Handles both the classic end-of-central-directory record and the zip64
variant (the year archives are zip64). Members stored with method 0
(stored) are returned as-is; method 8 (deflate) is inflated with
zlib wbits=-15.

Be polite to Zenodo: requests are sequential and retried with backoff on
429 / 5xx.
"""

import gzip
import json
import os
import struct
import time
import urllib.error
import urllib.request
import zlib

USER_AGENT = (
    "hot-alarm-inventory/1.0 (academic research; range-reads only, "
    "no bulk download)"
)

ZENODO_API = "https://zenodo.org/api/records/20204946"


# ---------------------------------------------------------------- transport

def _open(url, headers=None, timeout=180):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)


def http_get(url, headers=None, retries=6, timeout=180):
    """GET with backoff on 429 / 5xx / transient network errors."""
    delay = 2.0
    last = None
    for attempt in range(retries):
        try:
            resp = _open(url, headers=headers, timeout=timeout)
            return resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                wait = float(e.headers.get("Retry-After") or 0) or delay
                time.sleep(min(wait, 120))
                delay = min(delay * 2, 120)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError(f"giving up on {url} after {retries} attempts: {last!r}")


def fetch_range(url, start, end):
    """Inclusive byte range [start, end]."""
    data, _ = http_get(url, headers={"Range": f"bytes={start}-{end}"})
    return data


def remote_size(url):
    """Total object size, via a 1-byte ranged GET (HEAD can be redirected)."""
    _, hdrs = http_get(url, headers={"Range": "bytes=0-0"})
    cr = hdrs.get("Content-Range")
    if cr:
        return int(cr.split("/")[1])
    return int(hdrs["Content-Length"])


# ------------------------------------------------------------------- zip

def central_directory(url, size=None):
    """Return [(name, method, comp_size, uncomp_size, local_header_offset), ...]."""
    if size is None:
        size = remote_size(url)

    # EOCD (plus any zip64 locator/record) lives in the last chunk.
    tail_len = min(size, 1 << 20)
    tail = fetch_range(url, size - tail_len, size - 1)
    tail_base = size - tail_len

    i = tail.rfind(b"PK\x05\x06")
    if i < 0:
        raise ValueError(f"no end-of-central-directory found in {url}")
    cd_size = struct.unpack("<I", tail[i + 12:i + 16])[0]
    cd_off = struct.unpack("<I", tail[i + 16:i + 20])[0]

    if cd_off == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
        # zip64: prefer the locator, fall back to scanning for the EOCD64 record
        j = tail.rfind(b"PK\x06\x07")
        rec = -1
        if j >= 0:
            rec_abs = struct.unpack("<Q", tail[j + 8:j + 16])[0]
            if rec_abs >= tail_base:
                rec = rec_abs - tail_base
        if rec < 0 or tail[rec:rec + 4] != b"PK\x06\x06":
            rec = tail.rfind(b"PK\x06\x06")
        if rec < 0:
            raise ValueError(f"zip64 EOCD record not found in {url}")
        cd_size = struct.unpack("<Q", tail[rec + 40:rec + 48])[0]
        cd_off = struct.unpack("<Q", tail[rec + 48:rec + 56])[0]

    cd = fetch_range(url, cd_off, cd_off + cd_size - 1)

    entries = []
    p = 0
    while p + 46 <= len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method = struct.unpack("<H", cd[p + 10:p + 12])[0]
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nlen, elen, clen = struct.unpack("<HHH", cd[p + 28:p + 34])
        lho = struct.unpack("<I", cd[p + 42:p + 46])[0]
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + elen]

        q = 0
        while q + 4 <= len(extra):
            hid, hsz = struct.unpack("<HH", extra[q:q + 4])
            body = extra[q + 4:q + 4 + hsz]
            if hid == 1:
                r = 0
                if usize == 0xFFFFFFFF:
                    usize = struct.unpack("<Q", body[r:r + 8])[0]
                    r += 8
                if csize == 0xFFFFFFFF:
                    csize = struct.unpack("<Q", body[r:r + 8])[0]
                    r += 8
                if lho == 0xFFFFFFFF:
                    lho = struct.unpack("<Q", body[r:r + 8])[0]
                    r += 8
            q += 4 + hsz

        entries.append((name, method, csize, usize, lho))
        p += 46 + nlen + elen + clen

    return entries


def read_member(url, method, csize, lho):
    """Range-read one member's bytes and inflate if needed."""
    lh = fetch_range(url, lho, lho + 29)
    if lh[:4] != b"PK\x03\x04":
        raise ValueError(f"bad local file header at offset {lho} in {url}")
    nlen, elen = struct.unpack("<HH", lh[26:30])
    start = lho + 30 + nlen + elen
    raw = fetch_range(url, start, start + csize - 1)
    if method == 0:
        return raw
    if method == 8:
        return zlib.decompress(raw, -15)
    raise ValueError(f"unsupported compression method {method}")


# ------------------------------------------------------------------ cache

def cached_member(url, name, method, csize, lho, cache_dir, archive_tag):
    """read_member() with an on-disk cache so re-runs do not re-fetch.

    The cache is gzip-compressed: this machine is short on disk and the
    inflated alarm logs are ~460 MB across all years, ~35 MB gzipped.
    """
    safe = name.replace("/", "__")
    path = os.path.join(cache_dir, archive_tag, safe + ".gz")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            with gzip.open(path, "rb") as fh:
                return fh.read(), True
        except (OSError, EOFError):
            os.remove(path)  # truncated cache entry, refetch
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = read_member(url, method, csize, lho)
    tmp = path + ".part"
    with gzip.open(tmp, "wb", compresslevel=6) as fh:
        fh.write(data)
    os.replace(tmp, path)
    return data, False


def cached_central_directory(url, cache_dir, archive_tag):
    """Central directory listing, cached as JSON."""
    path = os.path.join(cache_dir, archive_tag, "_central_directory.json")
    if os.path.exists(path):
        with open(path) as fh:
            return [tuple(e) for e in json.load(fh)]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entries = central_directory(url)
    with open(path, "w") as fh:
        json.dump(entries, fh)
    return entries


def record_files(api_url=ZENODO_API):
    """{filename: content_url} from the Zenodo record API."""
    data, _ = http_get(api_url)
    rec = json.loads(data)
    out = {}
    for f in rec.get("files", []):
        links = f.get("links") or {}
        out[f["key"]] = links.get("content") or links.get("self")
    return out, rec
