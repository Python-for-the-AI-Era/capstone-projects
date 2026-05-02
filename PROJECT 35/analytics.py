import pandas as pd
import matplotlib.pyplot as plt

def generate_report(db_path):
    df = pd.read_sql("SELECT * FROM transactions", con=f"sqlite:///{db_path}")
    df['date'] = pd.to_datetime(df['date'])
    
    # Task 4: Monthly Summary Pivot
    report = df.pivot_table(
        index='category', 
        columns=df['date'].dt.strftime('%Y-%m'), 
        values='amount', 
        aggfunc='sum'
    ).fillna(0)
    
    # Save Bar Chart
    report.plot(kind='bar', figsize=(10, 6))
    plt.savefig("monthly_summary.png")
    return report