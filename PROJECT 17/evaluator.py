def calculate_catalog_coverage(recommendations, total_products):
    """
    What % of the 50,000 products were recommended at least once?
    If it's < 10%, the bias still exists.
    """
    unique_rec_products = set([p for user_recs in recommendations for p in user_recs])
    return (len(unique_rec_products) / total_products) * 100