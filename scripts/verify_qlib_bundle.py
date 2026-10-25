"""Verify the pinned community Qlib archive and its same-release manifest.

Run BEFORE extraction. Only metadata/checksums are inspected; no member content
is executed. Archive and contents remain in gitignored data/ directories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath


def verify(archive: Path, manifest_path: Path, expected_tag: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("release_tag") != expected_tag:
        raise ValueError("Manifest release tag mismatches requested immutable release")
    if manifest.get("archive_size_bytes") != archive.stat().st_size:
        raise ValueError("Archive size mismatches same-release manifest")
    digest = hashlib.sha256()
    with archive.open("rb") as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    actual = "sha256:" + digest.hexdigest()
    if manifest.get("archive_sha256") != actual:
        raise ValueError(f"Archive sha256 mismatch: got {actual}")
    members = 0
    unsafe = []
    first = []
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf:
            path = PurePosixPath(member.name)
            # Reject symlinks, hardlinks, devices and traversal. Data files only.
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                unsafe.append(member.name)
                continue
            if path.is_absolute() or ".." in path.parts or not path.parts:
                unsafe.append(member.name)
            if len(first) < 12:
                first.append(member.name)
            members += 1
    if unsafe:
        raise ValueError(f"Unsafe tar members: {unsafe[:10]}")
    if members < 20:
        raise ValueError("Archive has too few members to be a Qlib data package")
    return {
        "release_tag": expected_tag,
        "target_trade_date": manifest.get("target_trade_date"),
        "archive_sha256": actual,
        "archive_size_bytes": archive.stat().st_size,
        "member_count": members,
        "sample_members": first,
        "upstream_investment_data_commit": manifest.get("investment_data_commit"),
        "upstream_qlib_commit": manifest.get("qlib_commit"),
        "manifest_publisher_digest": manifest.get("image_digest"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = verify(args.archive, args.manifest, args.expected_tag)
    summary = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(summary + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
