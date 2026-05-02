import pandas as pd
import numpy as np
import random

def create_evidence_file():
    rows = 10000
    regions = ['Lagos', 'Abuja', 'Kano', 'Port Harcourt']
    
    data = {
        'region': [random.choice(regions) for _ in range(rows)],
        'revenue': [100.0] * rows  # Total should be 1,000,000
    }
    
    # Inject 3.7% "poison" data
    poison_indices = random.sample(range(rows), int(rows * 0.037))
    for idx in poison_indices:
        data['revenue'][idx] = random.choice(['N/A', '-', '', 'null'])
        
    df = pd.DataFrame(data)
    df.to_csv('daily_sales.csv', index=False)
    print("Generated daily_sales.csv with 3.7% corrupt rows.")

if __name__ == "__main__":
    create_evidence_file()