import pandas as pd
from unittest.mock import patch, MagicMock
import pytest
from sklearn.pipeline import Pipeline

from prometheus.regression import fit_lore_model

# Mock DataFrame to simulate database output
MOCK_DF = pd.DataFrame(
    {
        "gpm": [400, 410, 420, 430],
        "golddiffat15": [100, -50, 200, -100],
        "turrets_per_10": [1.2, 1.0, 1.5, 0.8],
        "baron_per_10": [0.2, 0.1, 0.3, 0.0],
        "dragon_per_10": [0.5, 0.6, 0.4, 0.7],
        "result": [1, 0, 1, 0],
    }
)


@patch("pandas.read_sql", return_value=MOCK_DF.copy())
def test_fit_lore_model_basic(mock_read_sql):
    pipeline, X_test, y_test = fit_lore_model(league="LCK", year=2022)
    assert isinstance(pipeline, Pipeline)
    assert X_test.shape[0] == y_test.shape[0]
    assert hasattr(pipeline.named_steps["regressor"], "coef_")


@patch("pandas.read_sql", return_value=pd.DataFrame())
def test_fit_lore_model_empty_df(mock_read_sql):
    with pytest.raises(ValueError):
        fit_lore_model(league="LCK", year=2022)
