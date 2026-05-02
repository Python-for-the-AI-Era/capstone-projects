# Code Review: Novex AI Document Service

## The "Lazy Loading" Trap
Explain how SQLAlchemy handles relationships by default and why "Lazy" loading is the enemy of high-concurrency APIs.

## Fix: selectinload vs. joinedload
- Why did you choose `selectinload` for the tags (Many-to-Many)?
- Why is `joinedload` potentially dangerous for large datasets (Cartesian products)?

## Performance Comparison
| Documents | Before Fix (Queries) | After Fix (Queries) | Time (10k docs) |
| :--- | :--- | :--- | :--- |
| 10 | 21 | 3 | 0.02s |
| 100 | 201 | 3 | 0.05s |
| 10,000 | 20,001 | 3 | 0.8s |

## Stretch Goal: Bulk Updates
Explain the difference between:
1. `for doc in docs: doc.status = 'archived'`
2. `update(Document).where(...).values(status='archived')`