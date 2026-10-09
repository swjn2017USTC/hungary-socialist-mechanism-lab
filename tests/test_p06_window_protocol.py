from __future__ import annotations

import pytest

from hsm_lab.calibration.window_protocol import (
    HashOnlyTarget,
    Phase,
    Window,
    WindowAccessRefused,
    WindowManifestEntry,
    guarded_value_read,
    hash_only_record,
)


def test_holdout_registry_projection_is_hash_only() -> None:
    target = HashOnlyTarget.from_registry(
        artifact_id="target-1979-1985",
        sha256="a" * 64,
    )
    record = hash_only_record(target)
    assert record == {
        "artifact_id": "target-1979-1985",
        "sha256": "a" * 64,
        "window": "holdout",
        "access": "hash_only",
    }
    assert not any("value" in key or "path" in key for key in record)


@pytest.mark.parametrize(
    ("window", "phase", "inference_complete", "entry"),
    [
        (Window.HOLDOUT, Phase.CALIBRATION, False, None),
        (Window.HOLDOUT, Phase.POST_INFERENCE_HOLDOUT_AUDIT, False, None),
        (Window.HOLDOUT, Phase.POST_INFERENCE_HOLDOUT_AUDIT, True, None),
        (Window.RESERVED, Phase.CALIBRATION, False, None),
        (Window.RESERVED, Phase.P06_RESERVED_EVALUATION, False, None),
    ],
)
def test_protected_window_refusal_happens_before_reader(
    window: Window,
    phase: Phase,
    inference_complete: bool,
    entry: WindowManifestEntry | None,
) -> None:
    reads: list[bool] = []

    def reader() -> str:
        reads.append(True)
        return "target values must not be reached"

    with pytest.raises(WindowAccessRefused):
        guarded_value_read(
            reader,
            window,
            phase,
            inference_complete=inference_complete,
            manifest_entry=entry,
        )
    assert reads == []


def test_holdout_requires_explicit_post_inference_manifest_before_read() -> None:
    entry = WindowManifestEntry(
        manifest_id="holdout-audit-001",
        window=Window.HOLDOUT,
        phase=Phase.POST_INFERENCE_HOLDOUT_AUDIT,
        declared_open=True,
    )
    reads: list[bool] = []
    assert guarded_value_read(
        lambda: reads.append(True) or "fixture",
        Window.HOLDOUT,
        Phase.POST_INFERENCE_HOLDOUT_AUDIT,
        inference_complete=True,
        manifest_entry=entry,
    ) == "fixture"
    assert reads == [True]


def test_reserved_requires_declared_p06_manifest_entry() -> None:
    # This exercises only authorization metadata; no reserved target is opened.
    entry = WindowManifestEntry(
        manifest_id="p06-reserved-open-001",
        window=Window.RESERVED,
        phase=Phase.P06_RESERVED_EVALUATION,
        declared_open=True,
    )
    from hsm_lab.calibration.window_protocol import authorize_value_read

    authorize_value_read(
        Window.RESERVED,
        Phase.P06_RESERVED_EVALUATION,
        manifest_entry=entry,
    )


@pytest.mark.parametrize("digest", ["", "f" * 63, "G" * 64])
def test_hash_only_projection_rejects_invalid_digest(digest: str) -> None:
    with pytest.raises(ValueError):
        HashOnlyTarget.from_registry(artifact_id="target", sha256=digest)
