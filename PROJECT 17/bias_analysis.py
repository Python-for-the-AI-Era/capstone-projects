import pandas as pd
import matplotlib.pyplot as plt

def plot_popularity_bias(df):
    """
    TASK: Plot the 'Long Tail' of ShopNaija.
    1. Count occurrences of every product in the orders table.
    2. Sort descending.
    3. Highlight the 'Head' (Top 20 items) vs the 'Tail' (50,000 items).
    """
    counts = df['product_id'].value_counts().values
    
    plt.figure(figsize=(10, 6))
    plt.plot(counts)
    plt.title("Product Popularity Distribution")
    plt.xlabel("Product Rank")
    plt.ylabel("Number of Purchases")
    # PROOF: The first 5-10 items will have 90% of the area under the curve.
    plt.show()