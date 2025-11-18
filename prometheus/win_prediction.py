import pandas as pd
import numpy as np

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    roc_auc_score,
    brier_score_loss,
    log_loss,
    accuracy_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from prometheus import DB_PATH
from prometheus.types import AURA_NUMERIC_BASE_FEATURES
from prometheus.players import _fetch_player_base_frame

SNAPSHOT_MINUTES = (10, 15, 20, 25)

_FEATURE_BASES = [
    ("gold", "goldat{m}"),
    ("xp", "xpat{m}"),
    ("cs", "csat{m}"),
    ("kills", "killsat{m}"),
    ("assists", "assistsat{m}"),
    ("deaths", "deathsat{m}"),
    ("opp_gold", "opp_goldat{m}"),
    ("opp_xp", "opp_xpat{m}"),
    ("opp_cs", "opp_csat{m}"),
    ("opp_kills", "opp_killsat{m}"),
    ("opp_assists", "opp_assistsat{m}"),
    ("opp_deaths", "opp_deathsat{m}"),
]


def _expand_player_snapshots_by_minute(
    df: pd.DataFrame, minutes: list[int] = SNAPSHOT_MINUTES
) -> pd.DataFrame:
    """Expand per-player snapshot row into multiple rows (one per minute mark).

    Parameters:
        df: DataFrame as returned by `_fetch_player_base_frame`.
        minutes: Minute marks to extract (must correspond to available snapshot columns).
    Returns:
        Expanded DataFrame with ordered columns and integer `result`.
    """
    id_cols = [
        c
        for c in ["gameid", "teamid", "playerid", "position", "result"]
        if c in df.columns
    ]
    expanded_parts: list[pd.DataFrame] = []
    for m in minutes:
        # Map each logical feature name to the concrete snapshot column.
        snapshot_values = {
            feat: df[col_tmpl.format(m=m)] for feat, col_tmpl in _FEATURE_BASES
        }
        part = df[id_cols].copy()
        for feat_name, series in snapshot_values.items():
            part[feat_name] = series
        part["minutes"] = m
        expanded_parts.append(part)
    out = pd.concat(expanded_parts, ignore_index=True)

    return out


def build_win_prediction_training_set(
    years: list[int] | None = None,
    minutes: list[int] = SNAPSHOT_MINUTES,
    db_path: str = DB_PATH,
) -> pd.DataFrame:
    """Create the training dataset for win probability modeling.

    Steps:
      1. Pull per-player snapshot rows from DB (optionally filtered by years).
      2. Expand snapshot columns (e.g., goldat10, goldat15, ...) into separate rows.
      3. Standardize column names & ordering; ensure binary target `result` is 0/1.

    Args:
        years: Filter matches by year(s); None => all available years.
        minutes: Snapshot minute marks to include (must exist in the schema).
        db_path: SQLite database path.
    Returns:
        DataFrame with one row per (player, game, minute mark).
    """
    base = _fetch_player_base_frame(years=years, db_path=db_path)
    return _expand_player_snapshots_by_minute(base, minutes=minutes)


def _add_difference_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add difference features (team - opponent) for core stats.

    Keeps originals (can help model capture scale) plus diffs for directional signal.
    """
    diff_pairs = [
        ("gold", "opp_gold"),
        ("xp", "opp_xp"),
        ("cs", "opp_cs"),
        ("kills", "opp_kills"),
        ("assists", "opp_assists"),
        ("deaths", "opp_deaths"),  # lower is better; diff will be negative if ahead
    ]
    for a, b in diff_pairs:
        df[f"{a}_diff"] = df[a] - df[b]
    return df


def _prepare_feature_matrix(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, list[str], list[str]]:
    """Return X, y along with numeric & categorical feature lists.

    Adds engineered difference features and includes snapshot minute mark.
    """
    work = _add_difference_features(df)

    # Numeric features: base numeric + engineered diffs + minutes
    diff_cols = [c for c in work.columns if c.endswith("_diff")]
    numeric_features = sorted(set(AURA_NUMERIC_BASE_FEATURES + diff_cols + ["minutes"]))
    categorical_features = ["position"]

    feature_cols = numeric_features + categorical_features
    X = work[feature_cols]
    y = work["result"].astype(int)
    X.columns = X.columns.map(str)  # ensure all str for sklearn
    return X, y, numeric_features, categorical_features


def _build_logistic_pipeline(
    numeric_features: list[str], categorical_features: list[str], classifier=None
) -> Pipeline:
    """Construct the modeling pipeline (default: tuned XGBoost) without scaling."""
    transformers = [
        ("num", "passthrough", numeric_features),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
    ]
    preprocessor = ColumnTransformer(transformers, remainder="drop")

    if classifier is None:
        classifier = XGBClassifier(
            learning_rate=0.05,
            max_depth=5,
            n_estimators=400,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            min_child_weight=1,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
        )

    pipe = Pipeline(
        steps=[
            ("pre", preprocessor),
            ("model", classifier),
        ]
    )
    return pipe


def _evaluate_binary_classifier(
    model: Pipeline, X: pd.DataFrame, y: pd.Series
) -> dict[str, float]:
    """Compute standard probability metrics for binary classification."""
    proba = model.predict_proba(X)[:, 1]
    preds = (proba >= 0.5).astype(int)
    metrics = {
        "roc_auc": float(roc_auc_score(y, proba)),
        "brier": float(brier_score_loss(y, proba)),
        "log_loss": float(log_loss(y, proba)),
        "accuracy": float(accuracy_score(y, preds)),
    }
    return metrics


def _evaluate_per_minute_metrics(model: Pipeline, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Compute metrics separately for each minute value in X['minutes'].

    Expects raw feature matrix (pre transformation) that still contains the
    'minutes' column. Returns a DataFrame sorted by minutes.
    """
    rows = [] 
    for minute_value, X_sub in X.groupby('minutes'):
        y_sub = y.loc[X_sub.index]
        m = _evaluate_binary_classifier(model, X_sub, y_sub)
        m['minutes'] = minute_value
        m['n_rows'] = len(X_sub)
        rows.append(m)
    dfm = pd.DataFrame(rows).sort_values('minutes').reset_index(drop=True)
    
    return dfm[['minutes','n_rows','accuracy','roc_auc','brier','log_loss']]


def _train_win_probability_model(
    years: list[int] | None = None,
    minutes: list[int] = SNAPSHOT_MINUTES,
    db_path: str = DB_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Train a logistic regression win probability model and report metrics.

    Splits on rows (player-minute snapshots). NOTE: this can leak match-level
    information across train/test if a single game contributes rows to both
    splits. For stricter evaluation, group by gameid and split groups; this can
    be added later.
    """
    df = build_win_prediction_training_set(
        years=years, minutes=minutes, db_path=db_path
    )
    X, y, num_feats, cat_feats = _prepare_feature_matrix(df)

    # Basic random split (optionally switch to group split later)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    pipe = _build_logistic_pipeline(num_feats, cat_feats)
    pipe.fit(X_train, y_train)

    train_metrics = _evaluate_binary_classifier(pipe, X_train, y_train)
    test_metrics = _evaluate_binary_classifier(pipe, X_test, y_test)
    per_minute_test = _evaluate_per_minute_metrics(pipe, X_test, y_test)

    return {
        "model": pipe,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "per_minute_test_metrics": per_minute_test,
        "numeric_features": num_feats,
        "categorical_features": cat_feats,
        "minutes_used": list(minutes),
        "rows": len(df),
    }
    
def get_prediction_model():
    info = _train_win_probability_model()
    return info['model']


if __name__ == "__main__":
    info = _train_win_probability_model()
    print("Train metrics:", info["train_metrics"])
    print("Test metrics:", info["test_metrics"])
    print("Per-minute test metrics:\n", info["per_minute_test_metrics"])
