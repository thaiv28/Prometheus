import pandas as pd
from sklearn.pipeline import Pipeline

from prometheus.regression import fit_glory_pipeline

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


def test_fit_glory_pipeline():
    features = [c for c in FEATURES if c != "result"]
    pipeline = fit_glory_pipeline(MOCK_DF, features)

    assert isinstance(pipeline, Pipeline)
    assert pipeline.named_steps["regressor"].coef_.shape == (len(features),)
