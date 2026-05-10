"""
Airflow DAG for Automated Model Retraining

This DAG runs weekly to detect model drift and automatically retrain
models when significant drift is detected.
"""

from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sensors.filesystem import FileSensor
from airflow.exceptions import AirflowException

# Import our custom modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_generator import CreditDataGenerator
from model_trainer import CreditModelTrainer
from drift_detector import DriftDetector
from model_registry import ModelRegistry
from alerting import SlackNotifier

logger = logging.getLogger(__name__)

# Default arguments for the DAG
default_args = {
    'owner': 'ml-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': ['ml-team@creditchek.com'],
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'catchup': False,
}

# Create the DAG
dag = DAG(
    'model_drift_detection_and_retraining',
    default_args=default_args,
    description='Weekly model drift detection and automated retraining',
    schedule_interval='@weekly',
    tags=['ml', 'drift', 'retraining'],
    max_active_runs=1,
)


def get_config(**kwargs):
    """Load configuration from environment variables."""
    from dotenv import load_dotenv
    import os
    
    # Load environment variables
    load_dotenv('/opt/airflow/.env')
    
    config = {
        'database_url': os.getenv('MODEL_REGISTRY_DB_URL', 'postgresql://airflow:airflow@postgres/model_registry'),
        'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
        'slack_channel': os.getenv('SLACK_CHANNEL', '#model-alerts'),
        'psi_threshold': float(os.getenv('PSI_THRESHOLD', '0.2')),
        'model_path': os.getenv('MODEL_PATH', '/opt/airflow/models'),
        'data_path': os.getenv('DATA_PATH', '/opt/airflow/data'),
        'production_data_days': int(os.getenv('PRODUCTION_DATA_DAYS', '30')),
    }
    
    # Push config to XCom for other tasks
    kwargs['ti'].xcom_push(key='config', value=config)
    
    logger.info(f"Configuration loaded: {config}")
    
    return config


def generate_training_data(**kwargs):
    """Generate training data for the model."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    
    logger.info("Generating training data...")
    
    # Initialize data generator
    data_generator = CreditDataGenerator(random_state=42)
    
    # Generate training data
    X_train, y_train = data_generator.generate_training_data(
        n_samples=10000,
        target_default_rate=0.15
    )
    
    # Save training data
    import pandas as pd
    train_data = X_train.copy()
    train_data['default'] = y_train
    
    train_path = f"{config['data_path']}/training_data.csv"
    train_data.to_csv(train_path, index=False)
    
    logger.info(f"Training data saved to {train_path}")
    logger.info(f"Training data shape: {train_data.shape}")
    logger.info(f"Default rate: {y_train.mean():.3f}")
    
    # Push data paths to XCom
    kwargs['ti'].xcom_push(key='train_data_path', value=train_path)
    
    return train_path


def generate_production_data(**kwargs):
    """Generate production data with drift patterns."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    
    logger.info("Generating production data...")
    
    # Initialize data generator
    data_generator = CreditDataGenerator(random_state=42)
    
    # Create external events for realistic drift
    external_events = data_generator.create_external_events()
    
    # Generate production data with gradual drift
    start_date = datetime.now() - timedelta(days=config['production_data_days'])
    
    X_prod, y_prod, metadata = data_generator.generate_production_data(
        n_samples=2000,
        start_date=start_date,
        drift_type="gradual",
        drift_magnitude=0.3,
        external_events=external_events
    )
    
    # Save production data
    import pandas as pd
    prod_data = X_prod.copy()
    prod_data['default'] = y_prod
    prod_data['application_date'] = metadata['application_date']
    prod_data['application_id'] = metadata['application_id']
    
    prod_path = f"{config['data_path']}/production_data.csv"
    prod_data.to_csv(prod_path, index=False)
    
    metadata_path = f"{config['data_path']}/production_metadata.csv"
    metadata.to_csv(metadata_path, index=False)
    
    logger.info(f"Production data saved to {prod_path}")
    logger.info(f"Production data shape: {prod_data.shape}")
    logger.info(f"Production default rate: {y_prod.mean():.3f}")
    
    # Push data paths to XCom
    kwargs['ti'].xcom_push(key='prod_data_path', value=prod_path)
    kwargs['ti'].xcom_push(key='metadata_path', value=metadata_path)
    
    return prod_path


def detect_model_drift(**kwargs):
    """Detect drift in the current model."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    train_data_path = kwargs['ti'].xcom_pull(key='train_data_path', task_ids='generate_training_data')
    prod_data_path = kwargs['ti'].xcom_pull(key='prod_data_path', task_ids='generate_production_data')
    
    logger.info("Detecting model drift...")
    
    # Load data
    import pandas as pd
    train_data = pd.read_csv(train_data_path)
    prod_data = pd.read_csv(prod_data_path)
    
    # Separate features and targets
    feature_columns = [col for col in train_data.columns if col not in ['default']]
    
    X_train = train_data[feature_columns]
    X_prod = prod_data[feature_columns]
    
    # Initialize drift detector
    drift_detector = DriftDetector(psi_threshold=config['psi_threshold'])
    
    # Calculate PSI
    psi_results = drift_detector.calculate_psi(
        reference_data=X_train,
        current_data=X_prod,
        feature_columns=feature_columns
    )
    
    logger.info(f"Drift detection completed")
    logger.info(f"Drifted features: {psi_results['drifted_count']}")
    logger.info(f"Max PSI: {psi_results['max_psi']:.3f}")
    
    # Save drift results
    import json
    drift_results_path = f"{config['data_path']}/drift_results.json"
    with open(drift_results_path, 'w') as f:
        json.dump(psi_results, f, indent=2, default=str)
    
    # Push results to XCom
    kwargs['ti'].xcom_push(key='psi_results', value=psi_results)
    kwargs['ti'].xcom_push(key='drift_results_path', value=drift_results_path)
    
    # Determine if retraining is needed
    needs_retraining = psi_results['drifted_count'] > 0 or psi_results['max_psi'] > config['psi_threshold']
    kwargs['ti'].xcom_push(key='needs_retraining', value=needs_retraining)
    
    logger.info(f"Retraining needed: {needs_retraining}")
    
    return psi_results


def train_new_model(**kwargs):
    """Train a new model if drift is detected."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    train_data_path = kwargs['ti'].xcom_pull(key='train_data_path', task_ids='generate_training_data')
    psi_results = kwargs['ti'].xcom_pull(key='psi_results', task_ids='detect_model_drift')
    needs_retraining = kwargs['ti'].xcom_pull(key='needs_retraining', task_ids='detect_model_drift')
    
    if not needs_retraining:
        logger.info("No retraining needed - skipping model training")
        kwargs['ti'].xcom_push(key='new_model_id', value=None)
        return None
    
    logger.info("Training new model due to detected drift...")
    
    # Load training data
    import pandas as pd
    train_data = pd.read_csv(train_data_path)
    
    X = train_data.drop('default', axis=1)
    y = train_data['default']
    
    # Initialize model trainer
    trainer = CreditModelTrainer(model_path=config['model_path'])
    
    # Prepare data
    X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(X, y)
    
    # Train model
    training_results = trainer.train_model(
        X_train, y_train, X_val, y_val,
        model_type="random_forest",
        hyperparameter_tuning=False  # Set to True for production
    )
    
    # Evaluate model
    evaluation_results = trainer.evaluate_model(X_test, y_test, save_plots=True)
    
    # Get new version number
    model_registry = ModelRegistry(config['database_url'])
    model_history = model_registry.get_model_history("credit_default_model")
    new_version = str(len(model_history) + 1)
    
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
        'feature_count': X.shape[1],
        'training_samples': len(X_train),
        'training_duration': 0.0,  # Would be measured in real implementation
        'description': f"Auto-retrained due to drift. Max PSI: {psi_results['max_psi']:.3f}",
        'hyperparameters': training_results.get('hyperparameters', {}),
        'feature_importance': evaluation_results['shap_analysis']['feature_importance']
    }
    
    # Register new model
    new_model_id = model_registry.register_model(
        model_name="credit_default_model",
        version=new_version,
        model_type="random_forest",
        model_object=trainer.model,
        performance_metrics=performance_metrics,
        metadata={
            'training_results': training_results,
            'evaluation_results': evaluation_results,
            'drift_trigger': psi_results,
            'retraining_reason': 'automatic_drift_detection'
        }
    )
    
    # Deploy new model
    deployment_success = model_registry.deploy_model(new_model_id, environment='production')
    
    if deployment_success:
        logger.info(f"New model deployed successfully: {new_model_id}")
    else:
        logger.error(f"Failed to deploy new model: {new_model_id}")
        raise AirflowException("Model deployment failed")
    
    # Record drift analysis
    model_registry.record_drift_analysis(
        model_version_id=new_model_id,
        analysis_type="psi",
        drift_results=psi_results,
        action_taken="retrained"
    )
    
    # Push results to XCom
    kwargs['ti'].xcom_push(key='new_model_id', value=new_model_id)
    kwargs['ti'].xcom_push(key='new_version', value=new_version)
    kwargs['ti'].xcom_push(key='performance_metrics', value=performance_metrics)
    
    logger.info(f"New model training completed: {new_model_id}")
    
    return new_model_id


def send_retraining_alerts(**kwargs):
    """Send alerts about model retraining."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    psi_results = kwargs['ti'].xcom_pull(key='psi_results', task_ids='detect_model_drift')
    new_model_id = kwargs['ti'].xcom_pull(key='new_model_id', task_ids='train_new_model')
    new_version = kwargs['ti'].xcom_pull(key='new_version', task_ids='train_new_model')
    performance_metrics = kwargs['ti'].xcom_pull(key='performance_metrics', task_ids='train_new_model')
    needs_retraining = kwargs['ti'].xcom_pull(key='needs_retraining', task_ids='detect_model_drift')
    
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
        model_version="current",
        drift_results=psi_results,
        action_taken="retrained" if needs_retraining else "monitored"
    )
    
    # Send retraining alert if model was retrained
    if new_model_id and needs_retraining:
        # Get old model metrics for comparison
        model_registry = ModelRegistry(config['database_url'])
        model_history = model_registry.get_model_history("credit_default_model")
        
        old_metrics = {}
        if len(model_history) > 1:
            old_model = model_history[1]  # Second most recent
            old_metrics = {
                'test_auc': old_model.get('test_auc', 0),
                'test_f1': old_model.get('test_f1', 0)
            }
        else:
            # Use baseline metrics
            old_metrics = {
                'test_auc': 0.88,  # Original performance
                'test_f1': 0.75
            }
        
        slack_notifier.send_retraining_alert(
            model_name="credit_default_model",
            old_version=str(len(model_history) - 1) if len(model_history) > 1 else "1.0",
            new_version=new_version,
            old_metrics=old_metrics,
            new_metrics=performance_metrics,
            drift_reason=f"Max PSI: {psi_results['max_psi']:.3f}, Drifted features: {psi_results['drifted_count']}"
        )
    
    logger.info("Alerts sent successfully")


def generate_monitoring_report(**kwargs):
    """Generate a comprehensive monitoring report."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    psi_results = kwargs['ti'].xcom_pull(key='psi_results', task_ids='detect_model_drift')
    new_model_id = kwargs['ti'].xcom_pull(key='new_model_id', task_ids='train_new_model')
    
    logger.info("Generating monitoring report...")
    
    # Initialize model registry
    model_registry = ModelRegistry(config['database_url'])
    
    # Get registry statistics
    registry_stats = model_registry.get_registry_stats()
    
    # Get models needing attention
    models_needing_attention = model_registry.get_models_needing_attention(
        drift_threshold=config['psi_threshold']
    )
    
    # Get performance comparison
    performance_df = model_registry.get_performance_comparison("credit_default_model")
    
    # Generate report
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_models': registry_stats['total_models'],
            'active_models': registry_stats['active_models'],
            'drifted_models': registry_stats['drifted_models'],
            'retrained_models': 1 if new_model_id else 0,
            'registry_size_mb': registry_stats['registry_size_mb']
        },
        'drift_analysis': psi_results,
        'models_needing_attention': models_needing_attention,
        'performance_comparison': performance_df.to_dict('records') if not performance_df.empty else []
    }
    
    # Save report
    import json
    report_path = f"{config['data_path']}/monitoring_report.json"
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2, default=str)
    
    logger.info(f"Monitoring report saved to {report_path}")
    
    # Push report to XCom
    kwargs['ti'].xcom_push(key='report_data', value=report_data)
    
    return report_path


def send_weekly_report(**kwargs):
    """Send weekly monitoring report to Slack."""
    config = kwargs['ti'].xcom_pull(key='config', task_ids='get_config')
    report_data = kwargs['ti'].xcom_pull(key='report_data', task_ids='generate_monitoring_report')
    
    if not config['slack_webhook_url']:
        logger.warning("No Slack webhook URL configured - skipping weekly report")
        return
    
    # Initialize Slack notifier
    slack_notifier = SlackNotifier(
        webhook_url=config['slack_webhook_url'],
        channel=config['slack_channel']
    )
    
    # Send weekly report
    slack_notifier.send_weekly_report(report_data)
    
    logger.info("Weekly report sent successfully")


# Define the tasks
get_config_task = PythonOperator(
    task_id='get_config',
    python_callable=get_config,
    dag=dag
)

generate_training_data_task = PythonOperator(
    task_id='generate_training_data',
    python_callable=generate_training_data,
    dag=dag
)

generate_production_data_task = PythonOperator(
    task_id='generate_production_data',
    python_callable=generate_production_data,
    dag=dag
)

detect_drift_task = PythonOperator(
    task_id='detect_model_drift',
    python_callable=detect_model_drift,
    dag=dag
)

train_model_task = PythonOperator(
    task_id='train_new_model',
    python_callable=train_new_model,
    dag=dag
)

send_alerts_task = PythonOperator(
    task_id='send_retraining_alerts',
    python_callable=send_retraining_alerts,
    dag=dag
)

generate_report_task = PythonOperator(
    task_id='generate_monitoring_report',
    python_callable=generate_monitoring_report,
    dag=dag
)

send_weekly_report_task = PythonOperator(
    task_id='send_weekly_report',
    python_callable=send_weekly_report,
    dag=dag
)

# Define task dependencies
get_config_task >> [generate_training_data_task, generate_production_data_task]
generate_training_data_task >> detect_drift_task
generate_production_data_task >> detect_drift_task
detect_drift_task >> train_model_task
detect_drift_task >> send_alerts_task
train_model_task >> send_alerts_task
detect_drift_task >> generate_report_task
generate_report_task >> send_weekly_report_task

# Add branching logic for retraining
from airflow.operators.python import BranchPythonOperator

def should_retrain(**kwargs):
    """Determine if retraining is needed based on drift detection."""
    needs_retraining = kwargs['ti'].xcom_pull(key='needs_retraining', task_ids='detect_model_drift')
    
    if needs_retraining:
        return 'train_new_model'
    else:
        return 'send_retraining_alerts'

should_retrain_branch = BranchPythonOperator(
    task_id='should_retrain',
    python_callable=should_retrain,
    dag=dag
)

# Update dependencies to include branching
detect_drift_task >> should_retrain_branch
should_retrain_branch >> train_model_task
should_retrain_branch >> send_alerts_task

# Alternative path when no retraining is needed
send_alerts_task >> generate_report_task
train_model_task >> generate_report_task
