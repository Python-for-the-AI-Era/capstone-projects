import pandas as pd

def format_output(raw_results):
    """
    TASK: Map the new JSON/DOM results back to the original CSV contract:
    Columns: [timestamp, product_name, current_price, discount, vendor]
    """
    df = pd.DataFrame(raw_results)
    # Ensure backward compatibility
    return df[['timestamp', 'name', 'price', 'discount', 'vendor']]