import pandas as pd
from sklearn.model_selection import train_test_split

def prepare_balanced_dataset(pidgin_csv, english_csv):
    """
    TASK: Mix the datasets. 
    Target Ratio: 30% Pidgin / 70% English.
    This ensures the model keeps its English proficiency 
    while learning Pidgin nuances.
    """
    df_pidgin = pd.read_csv(pidgin_csv)
    df_english = pd.read_csv(english_csv)
    
    combined_df = pd.concat([df_pidgin, df_english.sample(frac=0.3)])
    return train_test_split(combined_df, test_size=0.2)