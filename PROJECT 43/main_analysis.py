#!/usr/bin/env python3
"""
Main Analysis Script for CreditChek Model Drift Detection

This script demonstrates the complete workflow for detecting, diagnosing,
and remediating model drift in credit default prediction models.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data_generator import CreditDataGenerator
from model_trainer import CreditModelTrainer
from drift_detector import DriftDetector
from model_registry import ModelRegistry
from alerting import SlackNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up the environment and configuration."""
    # Load environment variables
    load_dotenv('.env')
    
    # Create necessary directories
    directories = ['data', 'models', 'logs', 'reports', 'reports/plots']
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Configuration
    config = {
        'database_url': os.getenv('MODEL_REGISTRY_DB_URL', 'sqlite:///model_registry.db'),
        'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
        'slack_channel': os.getenv('SLACK_CHANNEL', '#model-alerts'),
        'psi_threshold': float(os.getenv('PSI_THRESHOLD', '0.2')),
        'model_path': 'models/',
        'data_path': 'data/',
        'reports_path': 'reports/',
    }
    
    logger.info("Environment setup completed")
    return config

def generate_baseline_data(config):
    """Generate baseline training data and initial model."""
    logger.info("=== GENERATING BASELINE DATA AND MODEL ===")
    
    # Initialize data generator
    data_generator = CreditDataGenerator(random_state=42)
    
    # Generate training data (simulating initial model training)
    X_train, y_train = data_generator.generate_training_data(
        n_samples=10000,
        target_default_rate=0.15
    )
    
    # Generate validation data
    X_val, y_val = data_generator.generate_training_data(
        n_samples=2000,
        target_default_rate=0.15
    )
    
    # Save baseline data
    train_data = X_train.copy()
    train_data['default'] = y_train
    train_path = os.path.join(config['data_path'], 'baseline_training_data.csv')
    train_data.to_csv(train_path, index=False)
    
    val_data = X_val.copy()
    val_data['default'] = y_val
    val_path = os.path.join(config['data_path'], 'baseline_validation_data.csv')
    val_data.to_csv(val_path, index=False)
    
    logger.info(f"Baseline training data: {train_data.shape}")
    logger.info(f"Baseline validation data: {val_data.shape}")
    logger.info(f"Training default rate: {y_train.mean():.3f}")
    logger.info(f"Validation default rate: {y_val.mean():.3f}")
    
    return X_train, X_val, y_train, y_val

def train_baseline_model(config, X_train, X_val, y_train, y_val):
    """Train the baseline credit default model."""
    logger.info("=== TRAINING BASELINE MODEL ===")
    
    # Initialize model trainer
    trainer = CreditModelTrainer(model_path=config['model_path'])
    
    # Prepare data
    X_train_prep, X_val_prep, X_test, y_train_prep, y_val_prep, y_test = trainer.prepare_data(
        pd.concat([X_train, X_val]), pd.concat([y_train, y_val])
    )
    
    # Train model
    training_results = trainer.train_model(
        X_train_prep, y_train_prep, X_val_prep, y_val_prep,
        model_type="random_forest",
        hyperparameter_tuning=False
    )
    
    # Evaluate model
    evaluation_results = trainer.evaluate_model(X_test, y_test, save_plots=True)
    
    # Prepare performance metrics
    performance_metrics = {
        'train_auc': training_results['validation_metrics']['roc_auc'],
        'val_auc': training_results['validation_metrics']['roc_auc'],
        'test_auc': evaluation_results['test_metrics']['roc_auc'],
        'train_f1': training_results['validation_metrics']['f1_score'],
        'val_f1': training_results['validation_metrics']['f1_score'],
        'test_f1': evaluation_results['test_metrics']['f1_score'],
        'accuracy': evaluation_results['test_metrics']['accuracy'],
        'precision': evaluation_results['test_metrics']['precision'],
        'recall': evaluation_results['test_metrics']['recall'],
        'feature_count': X_train.shape[1],
        'training_samples': len(X_train_prep),
        'training_duration': 0.0,
        'description': "Initial baseline model",
        'hyperparameters': {},
        'feature_importance': evaluation_results['shap_analysis']['feature_importance']
    }
    
    # Initialize model registry
    model_registry = ModelRegistry(config['database_url'])
    
    # Register baseline model
    baseline_model_id = model_registry.register_model(
        model_name="credit_default_model",
        version="1.0",
        model_type="random_forest",
        model_object=trainer.model,
        performance_metrics=performance_metrics,
        metadata={
            'training_results': training_results,
            'evaluation_results': evaluation_results,
            'model_type': 'baseline'
        }
    )
    
    # Deploy baseline model
    deployment_success = model_registry.deploy_model(baseline_model_id, environment='production')
    
    logger.info(f"Baseline model trained and deployed: {baseline_model_id}")
    logger.info(f"Test AUC: {performance_metrics['test_auc']:.3f}")
    logger.info(f"Test F1: {performance_metrics['test_f1']:.3f}")
    
    return trainer, baseline_model_id, performance_metrics

def simulate_production_drift(config, data_generator):
    """Generate production data with drift patterns."""
    logger.info("=== SIMULATING PRODUCTION DRIFT ===")
    
    # Create external events for realistic drift
    external_events = data_generator.create_external_events()
    
    # Generate production data with gradual drift (3 months of data)
    start_date = datetime.now() - timedelta(days=90)
    
    X_prod, y_prod, metadata = data_generator.generate_production_data(
        n_samples=3000,
        start_date=start_date,
        drift_type="gradual",
        drift_magnitude=0.4,  # Significant drift
        external_events=external_events
    )
    
    # Save production data
    prod_data = X_prod.copy()
    prod_data['default'] = y_prod
    prod_data['application_date'] = metadata['application_date']
    prod_data['application_id'] = metadata['application_id']
    
    prod_path = os.path.join(config['data_path'], 'production_data.csv')
    prod_data.to_csv(prod_path, index=False)
    
    metadata_path = os.path.join(config['data_path'], 'production_metadata.csv')
    metadata.to_csv(metadata_path, index=False)
    
    logger.info(f"Production data generated: {prod_data.shape}")
    logger.info(f"Production default rate: {y_prod.mean():.3f}")
    logger.info(f"Date range: {metadata['application_date'].min()} to {metadata['application_date'].max()}")
    
    return X_prod, y_prod, metadata, external_events

def calculate_psi_drift(config, X_train, X_prod):
    """Calculate PSI for drift detection."""
    logger.info("=== CALCULATING PSI DRIFT ===")
    
    # Initialize drift detector
    drift_detector = DriftDetector(psi_threshold=config['psi_threshold'])
    
    # Calculate PSI for all features
    psi_results = drift_detector.calculate_psi(
        reference_data=X_train,
        current_data=X_prod,
        feature_columns=X_train.columns.tolist()
    )
    
    # Display results
    logger.info(f"PSI Analysis Results:")
    logger.info(f"Total features analyzed: {psi_results['total_features']}")
    logger.info(f"Drifted features: {psi_results['drifted_count']}")
    logger.info(f"Max PSI: {psi_results['max_psi']:.3f}")
    logger.info(f"Threshold: {psi_results['threshold']}")
    
    logger.info("Top 10 drifted features:")
    psi_scores = psi_results['psi_scores']
    sorted_features = sorted(psi_scores.items(), key=lambda x: x[1], reverse=True)
    
    for i, (feature, psi) in enumerate(sorted_features[:10]):
        status = "DRIFTED" if psi > config['psi_threshold'] else "STABLE"
        logger.info(f"  {i+1:2d}. {feature:20s}: PSI={psi:.3f} ({status})")
    
    # Save PSI results
    psi_results_path = os.path.join(config['reports_path'], 'psi_results.json')
    with open(psi_results_path, 'w') as f:
        json.dump(psi_results, f, indent=2, default=str)
    
    return drift_detector, psi_results

def analyze_shap_drift(config, trainer, drift_detector, X_train, X_prod):
    """Analyze SHAP feature importance drift."""
    logger.info("=== ANALYZING SHAP DRIFT ===")
    
    # Sample data for SHAP analysis
    sample_size = 1000
    X_train_sample = X_train.sample(n=sample_size, random_state=42)
    X_prod_sample = X_prod.sample(n=min(sample_size, len(X_prod)), random_state=42)
    
    # Analyze SHAP drift
    shap_results = drift_detector.analyze_shap_drift(
        reference_model=trainer.model,
        current_model=trainer.model,  # Same model, different data
        reference_data=X_train_sample,
        current_data=X_prod_sample,
        sample_size=sample_size
    )
    
    # Display SHAP drift results
    importance_comparison = shap_results['importance_comparison']
    
    logger.info(f"SHAP Analysis Results:")
    logger.info(f"Importance correlation: {importance_comparison['importance_correlation']:.3f}")
    logger.info(f"Significant SHAP drift features: {shap_results['shap_drift_metrics']['significant_drift_count']}")
    
    logger.info("Top 5 most changed features:")
    most_changed = importance_comparison['most_changed_features'][:5]
    for i, feature in enumerate(most_changed):
        logger.info(f"  {i+1}. {feature['feature']}: Change = {feature['importance_change']:+.4f}")
    
    # Save SHAP results
    shap_results_path = os.path.join(config['reports_path'], 'shap_results.json')
    with open(shap_results_path, 'w') as f:
        json.dump(shap_results, f, indent=2, default=str)
    
    return shap_results

def create_evidently_report(config, X_train, X_prod, y_train, y_prod):
    """Create Evidently drift report."""
    logger.info("=== CREATING EVIDENTLY REPORT ===")
    
    # Initialize drift detector
    drift_detector = DriftDetector()
    
    # Create Evidently report
    evidently_results = drift_detector.create_evidently_report(
        reference_data=X_train,
        current_data=X_prod,
        reference_target=y_train,
        current_target=y_prod,
        report_path=os.path.join(config['reports_path'], 'evidently_drift_report.html')
    )
    
    logger.info(f"Evidently report saved to {evidently_results['report_path']}")
    
    return evidently_results

def analyze_root_causes(config, metadata, external_events, psi_results):
    """Analyze root causes of drift."""
    logger.info("=== ANALYZING ROOT CAUSES ===")
    
    # Convert metadata to DataFrame if needed
    if isinstance(metadata, dict):
        metadata_df = pd.DataFrame(metadata)
    else:
        metadata_df = metadata
    
    # Analyze temporal patterns
    metadata_df['application_date'] = pd.to_datetime(metadata_df['application_date'])
    metadata_df['date'] = metadata_df['application_date'].dt.date
    
    # Group by date to see trends
    daily_stats = metadata_df.groupby('date').agg({
        'application_id': 'count',
        'drift_applied': 'first'
    }).rename(columns={'application_id': 'application_count'})
    
    # Find correlation with external events
    root_cause_analysis = {
        'external_events': [],
        'temporal_patterns': {},
        'feature_drift_correlation': {}
    }
    
    # Analyze external events impact
    for event in external_events:
        event_date = event['date']
        event_name = event['name']
        event_impact = event['impact']
        
        # Find applications around event time
        event_start = event_date - timedelta(days=7)
        event_end = event_date + timedelta(days=7)
        
        event_period_data = metadata_df[
            (metadata_df['application_date'] >= event_start) & 
            (metadata_df['application_date'] <= event_end)
        ]
        
        pre_event_data = metadata_df[
            (metadata_df['application_date'] >= event_start - timedelta(days=7)) & 
            (metadata_df['application_date'] < event_start)
        ]
        
        if len(event_period_data) > 0 and len(pre_event_data) > 0:
            volume_change = len(event_period_data) - len(pre_event_data)
            volume_change_pct = (volume_change / len(pre_event_data)) * 100
            
            root_cause_analysis['external_events'].append({
                'event_name': event_name,
                'event_date': event_date.isoformat(),
                'impact': event_impact,
                'volume_change': volume_change,
                'volume_change_pct': volume_change_pct,
                'affected_features': event.get('features', [])
            })
            
            logger.info(f"Event: {event_name}")
            logger.info(f"  Volume change: {volume_change_pct:+.1f}%")
            logger.info(f"  Affected features: {event.get('features', [])}")
    
    # Analyze which features drifted most and correlate with events
    drifted_features = psi_results['drifted_features']
    root_cause_analysis['drifted_features'] = drifted_features
    
    # Save root cause analysis
    root_cause_path = os.path.join(config['reports_path'], 'root_cause_analysis.json')
    with open(root_cause_path, 'w') as f:
        json.dump(root_cause_analysis, f, indent=2, default=str)
    
    logger.info(f"Root cause analysis completed")
    logger.info(f"Major drifted features: {drifted_features}")
    
    return root_cause_analysis

def demonstrate_retraining(config, X_train, X_prod, y_train, y_prod, baseline_model_id, baseline_metrics):
    """Demonstrate model retraining due to drift."""
    logger.info("=== DEMONSTRATING MODEL RETRAINING ===")
    
    # Initialize model trainer
    trainer = CreditModelTrainer(model_path=config['model_path'])
    
    # Prepare combined data for retraining
    X_retrain = pd.concat([X_train, X_prod])
    y_retrain = pd.concat([y_train, y_prod])
    
    # Prepare data splits
    X_train_prep, X_val_prep, X_test, y_train_prep, y_val_prep, y_test = trainer.prepare_data(
        X_retrain, y_retrain
    )
    
    # Train new model
    training_results = trainer.train_model(
        X_train_prep, y_train_prep, X_val_prep, y_val_prep,
        model_type="random_forest",
        hyperparameter_tuning=False
    )
    
    # Evaluate new model
    evaluation_results = trainer.evaluate_model(X_test, y_test, save_plots=True)
    
    # Prepare performance metrics
    new_performance_metrics = {
        'train_auc': training_results['validation_metrics']['roc_auc'],
        'val_auc': training_results['validation_metrics']['roc_auc'],
        'test_auc': evaluation_results['test_metrics']['roc_auc'],
        'train_f1': training_results['validation_metrics']['f1_score'],
        'val_f1': training_results['validation_metrics']['f1_score'],
        'test_f1': evaluation_results['test_metrics']['f1_score'],
        'accuracy': evaluation_results['test_metrics']['accuracy'],
        'precision': evaluation_results['test_metrics']['precision'],
        'recall': evaluation_results['test_metrics']['recall'],
        'feature_count': X_train.shape[1],
        'training_samples': len(X_train_prep),
        'training_duration': 0.0,
        'description': "Retrained model due to detected drift",
        'hyperparameters': {},
        'feature_importance': evaluation_results['shap_analysis']['feature_importance']
    }
    
    # Initialize model registry
    model_registry = ModelRegistry(config['database_url'])
    
    # Get new version number
    model_history = model_registry.get_model_history("credit_default_model")
    new_version = str(len(model_history) + 1)
    
    # Register new model
    new_model_id = model_registry.register_model(
        model_name="credit_default_model",
        version=new_version,
        model_type="random_forest",
        model_object=trainer.model,
        performance_metrics=new_performance_metrics,
        metadata={
            'training_results': training_results,
            'evaluation_results': evaluation_results,
            'retraining_reason': 'drift_detection_demo',
            'baseline_model_id': baseline_model_id
        }
    )
    
    # Deploy new model
    deployment_success = model_registry.deploy_model(new_model_id, environment='production')
    
    # Record drift analysis
    psi_results_path = os.path.join(config['reports_path'], 'psi_results.json')
    with open(psi_results_path, 'r') as f:
        psi_results = json.load(f)
    
    model_registry.record_drift_analysis(
        model_version_id=new_model_id,
        analysis_type="psi",
        drift_results=psi_results,
        action_taken="retrained"
    )
    
    # Compare performance
    auc_change = new_performance_metrics['test_auc'] - baseline_metrics['test_auc']
    f1_change = new_performance_metrics['test_f1'] - baseline_metrics['test_f1']
    
    logger.info(f"Model retraining completed: {new_model_id}")
    logger.info(f"Performance comparison:")
    logger.info(f"  AUC: {baseline_metrics['test_auc']:.3f} → {new_performance_metrics['test_auc']:.3f} ({auc_change:+.3f})")
    logger.info(f"  F1:  {baseline_metrics['test_f1']:.3f} → {new_performance_metrics['test_f1']:.3f} ({f1_change:+.3f})")
    
    return new_model_id, new_performance_metrics

def send_alerts(config, psi_results, baseline_model_id, new_model_id, baseline_metrics, new_metrics):
    """Send Slack alerts about drift and retraining."""
    logger.info("=== SENDING ALERTS ===")
    
    if not config['slack_webhook_url']:
        logger.warning("No Slack webhook URL configured - skipping alerts")
        return
    
    # Initialize Slack notifier
    slack_notifier = SlackNotifier(
        webhook_url=config['slack_webhook_url'],
        channel=config['slack_channel']
    )
    
    # Send drift alert
    slack_notifier.send_drift_alert(
        model_name="credit_default_model",
        model_version="1.0",
        drift_results=psi_results,
        action_taken="retrained"
    )
    
    # Send retraining alert
    if new_model_id:
        slack_notifier.send_retraining_alert(
            model_name="credit_default_model",
            old_version="1.0",
            new_version="2.0",
            old_metrics=baseline_metrics,
            new_metrics=new_metrics,
            drift_reason=f"Max PSI: {psi_results['max_psi']:.3f}, Drifted features: {psi_results['drifted_count']}"
        )
    
    logger.info("Alerts sent successfully")

def create_comprehensive_report(config, psi_results, shap_results, root_cause_analysis, 
                               baseline_metrics, new_metrics):
    """Create a comprehensive analysis report."""
    logger.info("=== CREATING COMPREHENSIVE REPORT ===")
    
    # Generate report summary
    report_summary = {
        'analysis_date': datetime.now().isoformat(),
        'model_name': 'credit_default_model',
        'baseline_version': '1.0',
        'retrained_version': '2.0',
        'drift_detection': {
            'psi_threshold': config['psi_threshold'],
            'total_features': psi_results['total_features'],
            'drifted_features': psi_results['drifted_count'],
            'max_psi': psi_results['max_psi'],
            'drifted_feature_list': psi_results['drifted_features']
        },
        'shap_analysis': {
            'importance_correlation': shap_results['importance_comparison']['importance_correlation'],
            'significant_shap_drift': shap_results['shap_drift_metrics']['significant_drift_count']
        },
        'root_causes': {
            'external_events_count': len(root_cause_analysis.get('external_events', [])),
            'major_events': [event['event_name'] for event in root_cause_analysis.get('external_events', [])]
        },
        'performance_comparison': {
            'baseline_auc': baseline_metrics['test_auc'],
            'retrained_auc': new_metrics['test_auc'],
            'auc_change': new_metrics['test_auc'] - baseline_metrics['test_auc'],
            'baseline_f1': baseline_metrics['test_f1'],
            'retrained_f1': new_metrics['test_f1'],
            'f1_change': new_metrics['test_f1'] - baseline_metrics['test_f1']
        },
        'recommendations': []
    }
    
    # Generate recommendations
    if psi_results['max_psi'] > 0.3:
        report_summary['recommendations'].append("High drift detected - consider more frequent monitoring")
    
    if new_metrics['test_auc'] < baseline_metrics['test_auc']:
        report_summary['recommendations'].append("Performance degraded - investigate data quality and feature engineering")
    
    if shap_results['importance_comparison']['importance_correlation'] < 0.7:
        report_summary['recommendations'].append("Feature importance shifted significantly - review model interpretability")
    
    # Save comprehensive report
    report_path = os.path.join(config['reports_path'], 'comprehensive_analysis_report.json')
    with open(report_path, 'w') as f:
        json.dump(report_summary, f, indent=2, default=str)
    
    logger.info(f"Comprehensive report saved to {report_path}")
    
    return report_summary

def create_visualizations(config, X_train, X_prod, psi_results):
    """Create visualization plots."""
    logger.info("=== CREATING VISUALIZATIONS ===")
    
    plots_dir = Path(config['reports_path']) / 'plots'
    plots_dir.mkdir(exist_ok=True)
    
    # PSI visualization
    psi_df = pd.DataFrame(list(psi_results['psi_scores'].items()), columns=['Feature', 'PSI'])
    psi_df = psi_df.sort_values('PSI', ascending=True)
    
    plt.figure(figsize=(12, 8))
    colors = ['red' if psi > config['psi_threshold'] else 'orange' if psi > 0.1 else 'green' 
             for psi in psi_df['PSI']]
    
    bars = plt.barh(psi_df['Feature'], psi_df['PSI'], color=colors, alpha=0.7)
    plt.axvline(x=config['psi_threshold'], color='red', linestyle='--', alpha=0.8, label=f'Drift Threshold ({config["psi_threshold"]})')
    plt.axvline(x=0.1, color='orange', linestyle='--', alpha=0.6, label='Warning Threshold (0.1)')
    
    plt.xlabel('Population Stability Index (PSI)', fontsize=12)
    plt.title('Model Drift Analysis - PSI Scores by Feature', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(axis='x', alpha=0.3)
    
    # Add value labels
    for i, (bar, psi) in enumerate(zip(bars, psi_df['PSI'])):
        plt.text(psi + 0.01, bar.get_y() + bar.get_height()/2, 
                f'{psi:.3f}', va='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(plots_dir / 'psi_drift_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Data distribution comparison
    feature_cols = X_train.columns.tolist()[:6]  # First 6 features
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    for i, feature in enumerate(feature_cols):
        if i >= len(axes):
            break
            
        axes[i].hist(X_train[feature], bins=30, alpha=0.7, label='Training', density=True)
        axes[i].hist(X_prod[feature], bins=30, alpha=0.7, label='Production', density=True)
        axes[i].set_title(f'{feature}')
        axes[i].set_xlabel('Value')
        axes[i].set_ylabel('Density')
        axes[i].legend()
        axes[i].grid(True, alpha=0.3)
    
    plt.suptitle('Feature Distribution Comparison: Training vs Production', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(plots_dir / 'feature_distribution_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Visualizations saved to {plots_dir}")

def main():
    """Main function to run the complete analysis."""
    logger.info("🚀 Starting CreditChek Model Drift Detection Analysis")
    
    # Setup environment
    config = setup_environment()
    
    try:
        # 1. Generate baseline data and train initial model
        X_train, X_val, y_train, y_val = generate_baseline_data(config)
        trainer, baseline_model_id, baseline_metrics = train_baseline_model(config, X_train, X_val, y_train, y_val)
        
        # 2. Simulate production drift
        data_generator = CreditDataGenerator(random_state=42)
        X_prod, y_prod, metadata, external_events = simulate_production_drift(config, data_generator)
        
        # 3. Calculate PSI drift
        drift_detector, psi_results = calculate_psi_drift(config, X_train, X_prod)
        
        # 4. Analyze SHAP drift
        shap_results = analyze_shap_drift(config, trainer, drift_detector, X_train, X_prod)
        
        # 5. Create Evidently report
        evidently_results = create_evidently_report(config, X_train, X_prod, y_train, y_prod)
        
        # 6. Analyze root causes
        root_cause_analysis = analyze_root_causes(config, metadata, external_events, psi_results)
        
        # 7. Demonstrate retraining
        new_model_id, new_metrics = demonstrate_retraining(config, X_train, X_prod, y_train, y_prod, 
                                                         baseline_model_id, baseline_metrics)
        
        # 8. Send alerts
        send_alerts(config, psi_results, baseline_model_id, new_model_id, baseline_metrics, new_metrics)
        
        # 9. Create comprehensive report
        report_summary = create_comprehensive_report(config, psi_results, shap_results, 
                                                   root_cause_analysis, baseline_metrics, new_metrics)
        
        # 10. Create visualizations
        create_visualizations(config, X_train, X_prod, psi_results)
        
        # Final summary
        logger.info("✅ ANALYSIS COMPLETED SUCCESSFULLY")
        logger.info(f"📊 Reports saved to: {config['reports_path']}")
        logger.info(f"🤖 Models saved to: {config['model_path']}")
        logger.info(f"💾 Data saved to: {config['data_path']}")
        
        # Display key results
        print("\n" + "="*80)
        print("🎯 CREDITCHIEK MODEL DRIFT ANALYSIS RESULTS")
        print("="*80)
        print(f"📈 Baseline Model AUC: {baseline_metrics['test_auc']:.3f}")
        print(f"🔄 Retrained Model AUC: {new_metrics['test_auc']:.3f}")
        print(f"📊 AUC Change: {new_metrics['test_auc'] - baseline_metrics['test_auc']:+.3f}")
        print(f"🔍 Max PSI: {psi_results['max_psi']:.3f}")
        print(f"⚠️  Drifted Features: {psi_results['drifted_count']}")
        print(f"📋 Drifted Features: {', '.join(psi_results['drifted_features'][:3])}")
        if len(psi_results['drifted_features']) > 3:
            print(f"     ... and {len(psi_results['drifted_features']) - 3} more")
        print(f"🔗 SHAP Importance Correlation: {shap_results['importance_comparison']['importance_correlation']:.3f}")
        print(f"🎪 External Events: {len(root_cause_analysis.get('external_events', []))}")
        print("="*80)
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise

if __name__ == "__main__":
    main()
