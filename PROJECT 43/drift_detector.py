import numpy as np
import pandas as pd

def calculate_psi(expected, actual, buckets=10):
    """Calculate the PSI between training (expected) and production (actual) data."""
    def get_probs(data):
        return np.histogram(data, bins=buckets)[0] / len(data)

    expected_probs = get_probs(expected)
    actual_probs = get_probs(actual)
    
    # Avoid division by zero
    actual_probs = np.where(actual_probs == 0, 0.0001, actual_probs)
    expected_probs = np.where(expected_probs == 0, 0.0001, expected_probs)
    
    psi_values = (expected_probs - actual_probs) * np.log(expected_probs / actual_probs)
    return np.sum(psi_values)

# Task 1: Audit top features
# If psi > 0.2, the feature (e.g., 'monthly_income') has drifted significantly.