from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


def fit_glory_pipeline(games, features):
    """Fit GLORY's StandardScaler + LinearRegression(result) pipeline on per-game rows."""
    pipeline = Pipeline(
        [("scaler", StandardScaler()), ("regressor", LinearRegression())]
    )
    return pipeline.fit(games[features], games["result"].astype(int))

