def temporal_split(df, date_col, threshold_date):
    """
    TASK: Instead of random shuffling, split by time.
    Train: Everything before January 2026.
    Test: Everything after January 2026.
    This prevents 'Look-ahead Bias'.
    """
    train = df[df[date_col] < threshold_date]
    test = df[df[date_col] >= threshold_date]
    return train, test