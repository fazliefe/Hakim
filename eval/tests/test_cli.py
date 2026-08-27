from __future__ import annotations

import json

from hakim_bench.cli import main
from hakim_bench.dataset import TARGET_MIX


def test_mix_only_prints_phase0_counts(capsys) -> None:
    assert main(["--mix-only"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n"] == 400
    for qtype, target in TARGET_MIX.items():
        assert abs(payload["share"][qtype] - target) <= 0.001
