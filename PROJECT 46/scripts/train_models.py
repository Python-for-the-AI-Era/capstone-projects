#!/usr/bin/env python3
"""
Model training script for property price prediction.

This script trains the XGBoost and LightGBM models with hyperparameter
optimization and saves the trained models for API deployment.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from data.generate_dataset import NigerianPropertyDataGenerator
from utils.feature_engineering import PropertyFeatureEngineer
from models.train_model import train_complete_pipeline, evaluate_model_performance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description='Train property price prediction models')
    parser.add_argument('--data-size', type=int, default=10000, help='Number of properties to generate')
    parser.add_argument('--n-trials', type=int, default=50, help='Number of Optuna trials')
    parser.add_argument('--output-dir', type=str, default='models', help='Output directory for models')
    parser.add_argument('--random-state', type=int, default=42, help='Random state')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting property price prediction model training...")
    logger.info(f"Configuration: data_size={args.data_size}, n_trials={args.n_trials}")
    
    try:
        # Step 1: Generate synthetic data
        logger.info("Step 1: Generating synthetic Nigerian property data...")
        generator = NigerianPropertyDataGenerator(args.data_size)
        df = generator.generate_dataset()
        
        # Get data summary
        summary = generator.get_data_summary(df)
        logger.info(f"Generated dataset: {summary['total_properties']:,} properties")
        logger.info(f"Price range: ₦{summary['price_stats']['min_price']:,.0f} - ₦{summary['price_stats']['max_price']:,.0f}")
        
        # Step 2: Feature engineering
        logger.info("Step 2: Performing feature engineering...")
        feature_engineer = PropertyFeatureEngineer()
        df_transformed = feature_engineer.fit_transform(df)
        
        logger.info(f"Feature engineering completed. Features: {len(feature_engineer.feature_names)}")
        
        # Step 3: Split data
        logger.info("Step 3: Splitting data into train/test sets...")
        from sklearn.model_selection import train_test_split
        
        X = df_transformed[feature_engineer.feature_columns]
        y = df_transformed['total_price_naira']
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=args.test_size, random_state=args.random_state
        )
        
        logger.info(f"Train set: {len(X_train):,} properties")
        logger.info(f"Test set: {len(X_test):,} properties")
        
        # Step 4: Train models
        logger.info("Step 4: Training models with hyperparameter optimization...")
        trainer = train_complete_pipeline(
            df_transformed,
            target_column='total_price_naira',
            feature_columns=feature_engineer.feature_columns,
            n_trials=args.n_trials,
            random_state=args.random_state
        )
        
        # Step 5: Evaluate on test set
        logger.info("Step 5: Evaluating models on test set...")
        test_metrics = evaluate_model_performance(trainer, X_test, y_test)
        
        # Step 6: Save models
        logger.info("Step 6: Saving models and artifacts...")
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save models
        trainer.save_models(output_dir)
        
        # Save feature engineer
        feature_engineer.save_transformers(output_dir / "transformers.pkl")
        
        # Save test results
        import json
        results = {
            'training_config': {
                'data_size': args.data_size,
                'n_trials': args.n_trials,
                'random_state': args.random_state,
                'test_size': args.test_size
            },
            'data_summary': summary,
            'feature_engineering': {
                'total_features': len(feature_engineer.feature_names),
                'feature_names': feature_engineer.feature_names
            },
            'model_performance': trainer.evaluation_results,
            'test_performance': test_metrics,
            'training_date': datetime.now().isoformat()
        }
        
        with open(output_dir / "training_results.json", 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Step 7: Print summary
        logger.info("Training completed successfully!")
        print("\n" + "="*60)
        print("TRAINING SUMMARY")
        print("="*60)
        print(f"Dataset: {summary['total_properties']:,} properties")
        print(f"Features: {len(feature_engineer.feature_names)} engineered features")
        print(f"Training samples: {len(X_train):,}")
        print(f"Test samples: {len(X_test):,}")
        print(f"Optuna trials: {args.n_trials}")
        print(f"\nModel Performance:")
        print(f"  Validation MAPE: {trainer.evaluation_results['XGBoost']['val']['val_mape']:.4f}")
        print(f"  Validation R²: {trainer.evaluation_results['XGBoost']['val']['val_r2']:.4f}")
        print(f"  Test MAPE: {test_metrics['test_mape']:.4f}")
        print(f"  Test R²: {test_metrics['test_r2']:.4f}")
        print(f"  Confidence Coverage: {test_metrics['confidence_coverage']:.4f}")
        print(f"  Avg Confidence Width: {test_metrics['avg_confidence_width_pct']:.2f}%")
        print(f"\nBest XGBoost Parameters:")
        for param, value in trainer.xgb_params.items():
            print(f"  {param}: {value}")
        print(f"\nModels saved to: {output_dir}")
        print("="*60)
        
        logger.info("Training pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == '__main__':
    main()
