from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from prometheus.matches import get_matches_frame

def fit_lore_model(region=None, year=None, evaluate=False):
    """
    Reads from match_lore_stats table, filters by region and year, and trains a logistic regression model to predict win probability.
    Args:
        region (str, optional): League/region to filter by (e.g., 'LCK').
        year (int, optional): Year to filter by (e.g., 2022).
    Returns:
        model: Trained scikit-learn logistic regression model.
        X_test: Test features.
        y_test: Test labels.
    """
    filters = {}
    if region:
        filters['region'] = region
    if year:
        filters['year'] = year
    df = get_matches_frame('match_lore_stats', filters)
    if df.empty:
        raise ValueError("No data found for given criteria.")
    
    feature_cols = ['gpm', 'golddiffat15', 'turrets_per_10', 'baron_per_10', 'dragon_per_10']
    X = df[feature_cols]
    y = df['result'].astype(int)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    if evaluate:
        _evaluate_model(model, X_test, y_test)
    
    return model, X_test, y_test

def _evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_pred_binary = (y_pred > 0.5).astype(int)
    acc = accuracy_score(y_test, y_pred_binary)
    print(f"Accuracy: {acc:.3f}")

    import matplotlib.pyplot as plt
    # Prepare colors: red for loss (0), blue for win (1)
    colors = ['red' if actual == 0 else 'blue' for actual in y_test]
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
    model, X_test, y_test = fit_lore_model(region='LPL', year=2018, evaluate=True)