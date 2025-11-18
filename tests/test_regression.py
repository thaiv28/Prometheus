import pandas as pd
from unittest.mock import patch, MagicMock
import pytest
from sklearn.pipeline import Pipeline

from prometheus.regression import _fit_glory_model

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
FEATURES = MOCK_DF.columns.tolist()


@patch("prometheus.regression.get_matches_frame", return_value=MOCK_DF.copy())
def test_fit_glory_model_basic(mock_get_matches_frame):
    pipeline, X_test, y_test = _fit_glory_model(
        FEATURES, leagues="LCK", years=2022, test_split=True
    )

    assert isinstance(pipeline, Pipeline)
    assert X_test.shape[0] == y_test.shape[0]
    assert hasattr(pipeline.named_steps["regressor"], "coef_")
