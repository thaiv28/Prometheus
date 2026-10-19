import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import elo_glicko_scale as joint


def test_stage2_preserves_major_and_international_update_scale():
    protected = set(joint.scale.em.MAJORS) | set(joint.scale.INTERNATIONAL_LEAGUES)
    leagues = protected | {"LFL", "NACL"}
    rd = joint.stage1_grid()[0]
    grid = joint.stage2_grid(leagues, rd)
    assert len(grid) == 16
    for _, kw in grid:
        for league in protected:
            assert (
                kw["league_slopes"].get(league, math.log(10) / 400)
                == math.log(10) / 400
            )
            assert 20 * kw["league_factors"].get(league, 1) == 20
        assert set(kw["league_slopes"]) == {"LFL", "NACL"}
        assert set(kw["league_factors"]) == {"LFL", "NACL"}
        for key, value in rd.items():
            assert kw[key] == value
