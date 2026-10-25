"""Offline tests for pinned dataset integrity and research uncertainty utilities."""

import hashlib
import io
import json
import tarfile

import numpy as np
import pandas as pd
import pytest

from quant_lab.experiment_analysis import paired_block_mean_interval
from scripts.verify_qlib_bundle import verify


def _build_archive(tmp_path, *, unsafe=False):
    archive = tmp_path / "qlib_bin.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for i in range(22):
            name = f"qlib_bin/features/asset{i}/close.day.bin"
            payload = b"1234"
            item = tarfile.TarInfo(name)
            item.size = len(payload)
            tf.addfile(item, io.BytesIO(payload))
        if unsafe:
            item = tarfile.TarInfo("qlib_bin/malicious")
            item.type = tarfile.SYMTYPE
            item.linkname = "/etc/passwd"
            tf.addfile(item)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "release_tag": "2026-10-25",
        "target_trade_date": "2026-10-23",
        "archive_size_bytes": archive.stat().st_size,
        "archive_sha256": "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    return archive, manifest


def test_same_release_integrity_and_manifest(tmp_path):
    tarball, manifest = _build_archive(tmp_path)
    result = verify(tarball, manifest, "2026-10-25")
    assert result["member_count"] == 22
    assert result["target_trade_date"] == "2026-10-23"
    with pytest.raises(ValueError, match="release tag"):
        verify(tarball, manifest, "2026-10-24")
    data = json.loads(manifest.read_text())
    data["archive_size_bytes"] = 1
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="size"):
        verify(tarball, manifest, "2026-10-25")


def test_reject_unsafe_link_in_data_archive(tmp_path):
    tarball, manifest = _build_archive(tmp_path, unsafe=True)
    with pytest.raises(ValueError, match="Unsafe tar members"):
        verify(tarball, manifest, "2026-10-25")


def test_block_bootstrap_is_deterministic_and_paired():
    a = pd.Series(np.linspace(-0.005, 0.005, 60))
    b = pd.Series(np.zeros(60))
    x = paired_block_mean_interval(a, b, block=5, draws=150, seed=7)
    y = paired_block_mean_interval(a, b, block=5, draws=150, seed=7)
    assert x == y
    assert x["n_sessions"] == 60
    assert x["bootstrap_95pct_mean_daily_diff"][0] <= x["bootstrap_95pct_mean_daily_diff"][1]
    with pytest.raises(ValueError, match="Paired"):
        paired_block_mean_interval(a[:3], b[:3], block=5, draws=150, seed=7)
