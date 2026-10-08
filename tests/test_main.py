from typer.testing import CliRunner

from prometheus import forge
from prometheus.main import app


def test_weights_prints_the_published_forecast_weights():
    result = CliRunner().invoke(app, ["weights"], terminal_width=200)

    assert result.exit_code == 0
    assert f"{forge.load_weights()['elo_weight']:.6f}" in result.output
    assert "turrets_per_10" in result.output
