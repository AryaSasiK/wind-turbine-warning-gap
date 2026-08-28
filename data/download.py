#!/usr/bin/env python3
"""Download Kelmarsh + Penmanshiel Zenodo records, verify md5, write manifest."""
import hashlib, json, os, subprocess, sys, time

RAW = os.environ.get("WTWG_RAW", "wind-turbine-warning-gap-data/raw")
RECORDS = {"kelmarsh": 16807551, "penmanshiel": 16807304}


def md5(path, bs=1 << 22):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bs), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest = {"downloaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "records": {}}
    for name, rid in RECORDS.items():
        meta = json.loads(subprocess.run(
            ["curl", "-sS", f"https://zenodo.org/api/records/{rid}"],
            capture_output=True, text=True, check=True).stdout)
        d = os.path.join(RAW, name)
        os.makedirs(d, exist_ok=True)
        files = []
        for f in sorted(meta["files"], key=lambda x: x["key"]):
            key, size, cks = f["key"], f["size"], f["checksum"].split(":", 1)[1]
            dest = os.path.join(d, key)
            if os.path.exists(dest) and os.path.getsize(dest) == size and md5(dest) == cks:
                status = "cached-ok"
            else:
                url = f["links"]["self"]
                print(f"[{name}] {key} ({size/1e6:.1f} MB)", flush=True)
                r = subprocess.run(["curl", "-sSL", "--retry", "5", "--retry-delay", "3",
                                    "-o", dest, url])
                if r.returncode != 0:
                    status = "download-failed"
                else:
                    got = md5(dest)
                    status = "ok" if got == cks else f"MD5-MISMATCH got={got}"
            print(f"   -> {status}", flush=True)
            files.append({"key": key, "size": size, "md5": cks, "status": status})
        manifest["records"][name] = {
            "record_id": rid,
            "record_url": f"https://zenodo.org/records/{rid}",
            "doi": meta["doi"],
            "concept_doi": meta.get("conceptdoi"),
            "version_label": meta["metadata"].get("version"),
            "publication_date": meta["metadata"].get("publication_date"),
            "zenodo_updated": meta.get("updated"),
            "license": meta["metadata"].get("license", {}).get("id"),
            "creators": [c["name"] for c in meta["metadata"].get("creators", [])],
            "title": meta["metadata"].get("title"),
            "total_bytes": sum(f["size"] for f in meta["files"]),
            "files": files,
        }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MANIFEST.json")
    with open(out, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("manifest ->", out)


if __name__ == "__main__":
    main()
