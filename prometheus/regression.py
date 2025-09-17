from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from prometheus.matches import get_matches_frame


def _fit_lore_model(features, league=None, year=None, evaluate=False):
    """
    Reads from match_lore_stats table, filters by league and year, and trains a linear regression model to predict win probability.
    The model is implemented as a scikit-learn pipeline that first scales features using StandardScaler,
    then fits a LinearRegression model. The pipeline can be used for prediction and will automatically scale input features.

    Args:
        league (str, optional): League/region to filter by (e.g., 'LCK').
        year (int, optional): Year to filter by (e.g., 2022).
        evaluate (bool, optional): If True, prints model weights and accuracy, and shows a plot of predicted scores.

    Returns:
        pipeline: Trained scikit-learn Pipeline (StandardScaler + LinearRegression).
        X_test: Test features (unscaled).
        y_test: Test labels.
    """
    filters = {}
    if league:
        filters["league"] = league
    if year:
        filters["year"] = year
    df = get_matches_frame("match_lore_stats", filters)

    X = df[features]
    y = df["result"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = Pipeline(
        [("scaler", StandardScaler()), ("regressor", LinearRegression())]
    )
    pipeline.fit(X_train, y_train)

    if evaluate:
        print(f"Evaluating model for league={league}, year={year}")
        print(
            f"Model weights: {pipeline.named_steps['regressor'].coef_}, Intercept: {pipeline.named_steps['regressor'].intercept_}"
        )
        _evaluate_model(pipeline, X_test, y_test)

    return pipeline, X_test, y_test


def _evaluate_model(pipeline, X_test, y_test):
    y_pred = pipeline.predict(X_test)
    y_pred_binary = (y_pred > 0.5).astype(int)
    acc = accuracy_score(y_test, y_pred_binary)
    print(f"Accuracy: {acc:.3f}")

    import matplotlib.pyplot as plt

    # Prepare colors: red for loss (0), blue for win (1)
    colors = ["red" if actual == 0 else "blue" for actual in y_test]
    # Plot 1D line with colored points for each score
    plt.figure(figsize=(10, 2))
    y_line = [1] * len(y_pred)  # All points on y=1
    plt.scatter(y_pred, y_line, c=colors, alpha=0.7, s=40)
    plt.yticks([])
    plt.xlabel("Predicted Score")
    plt.title("Predicted Win Score (Red=Loss, Blue=Win)")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    model, X_test, y_test = fit_lore_model(league="LPL", year=2018, evaluate=True)
