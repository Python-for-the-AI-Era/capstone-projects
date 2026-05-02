import polars as pl

# Task 4: Polars Streaming
q = (
    pl.scan_csv("large_data.csv")
    .filter(pl.col("amount") > 1000)
    .group_by("customer_region")
    .agg(pl.sum("amount"))
)

# streaming=True allows Polars to use the disk as temporary RAM
result = q.collect(streaming=True)