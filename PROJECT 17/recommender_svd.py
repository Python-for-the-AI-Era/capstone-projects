from surprise import SVD, Dataset, Reader
from surprise.model_selection import train_test_split

def train_svd_model(df):
    # Reader defines the rating scale (1-5 or just 1 for interaction)
    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[['user_id', 'product_id', 'rating']], reader)
    
    trainset, testset = train_test_split(data, test_size=0.2)
    
    # SVD uncovers hidden patterns in user behavior
    model = SVD(n_factors=100, n_epochs=20, lr_all=0.005, reg_all=0.02)
    model.fit(trainset)
    return model