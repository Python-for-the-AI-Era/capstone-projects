"""
Model Registry System for Credit Default Models

This module provides a comprehensive model registry for tracking model versions,
performance metrics, and metadata using SQLAlchemy for database persistence.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
import joblib
import pandas as pd

logger = logging.getLogger(__name__)

Base = declarative_base()


class ModelVersion(Base):
    """Model version table for tracking model metadata and performance."""
    
    __tablename__ = 'model_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    model_type = Column(String(50), nullable=False)
    status = Column(String(20), default='training')  # training, active, deprecated, failed
    
    # Performance metrics
    train_auc = Column(Float)
    val_auc = Column(Float)
    test_auc = Column(Float)
    train_f1 = Column(Float)
    val_f1 = Column(Float)
    test_f1 = Column(Float)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    
    # Model metadata
    feature_count = Column(Integer)
    training_samples = Column(Integer)
    training_duration = Column(Float)  # in seconds
    model_size_mb = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime)
    deprecated_at = Column(DateTime)
    
    # File paths and metadata
    model_path = Column(String(500))
    metadata_path = Column(String(500))
    description = Column(Text)
    hyperparameters = Column(Text)  # JSON string
    feature_importance = Column(Text)  # JSON string
    
    # Drift information
    drift_score = Column(Float)
    last_drift_check = Column(DateTime)
    drift_status = Column(String(20), default='unknown')  # unknown, detected, stable
    
    __table_args__ = (
        {'schema': 'model_registry'}
    )


class ModelDeployment(Base):
    """Model deployment tracking table."""
    
    __tablename__ = 'model_deployments'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(UUID(as_uuid=True), nullable=False)
    deployment_environment = Column(String(50), nullable=False)  # dev, staging, prod
    
    # Deployment metrics
    deployment_time = Column(DateTime, default=datetime.utcnow)
    rollback_time = Column(DateTime)
    deployment_status = Column(String(20), default='deployed')  # deployed, rolled_back, failed
    
    # Performance after deployment
    post_deployment_auc = Column(Float)
    post_deployment_f1 = Column(Float)
    monitoring_metrics = Column(Text)  # JSON string
    
    # Deployment metadata
    deployed_by = Column(String(100))
    deployment_notes = Column(Text)
    
    __table_args__ = (
        {'schema': 'model_registry'}
    )


class DriftAnalysis(Base):
    """Drift analysis tracking table."""
    
    __tablename__ = 'drift_analyses'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Analysis metadata
    analysis_date = Column(DateTime, default=datetime.utcnow)
    analysis_type = Column(String(50), nullable=False)  # psi, shap, evidently, temporal
    
    # Drift metrics
    drift_score = Column(Float)
    drifted_features_count = Column(Integer)
    total_features = Column(Integer)
    max_psi = Column(Float)
    
    # Detailed results
    drift_results = Column(Text)  # JSON string
    feature_drift_details = Column(Text)  # JSON string
    
    # Action taken
    action_taken = Column(String(50))  # none, retrained, deprecated, monitored
    action_timestamp = Column(DateTime)
    
    __table_args__ = (
        {'schema': 'model_registry'}
    )


class ModelRegistry:
    """
    Comprehensive model registry for tracking ML model lifecycle.
    
    This class provides database-backed model versioning, performance tracking,
    and deployment management for credit default models.
    """
    
    def __init__(self, database_url: str, model_storage_path: str = "models/"):
        """
        Initialize the model registry.
        
        Args:
            database_url: SQLAlchemy database connection string
            model_storage_path: Path to store model files
        """
        self.database_url = database_url
        self.model_storage_path = Path(model_storage_path)
        self.model_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables
        self._create_tables()
        
        logger.info(f"Model registry initialized with database: {database_url}")
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created/verified")
    
    def register_model(
        self,
        model_name: str,
        version: str,
        model_type: str,
        model_object: Any,
        performance_metrics: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new model version in the registry.
        
        Args:
            model_name: Name of the model
            version: Model version string
            model_type: Type of model (random_forest, gradient_boosting, etc.)
            model_object: Trained model object
            performance_metrics: Dictionary of performance metrics
            metadata: Additional metadata
            
        Returns:
            Model version ID
        """
        session = self.SessionLocal()
        
        try:
            # Save model file
            model_dir = self.model_storage_path / f"{model_name}_v{version}"
            model_dir.mkdir(exist_ok=True)
            
            model_file = model_dir / "model.joblib"
            joblib.dump(model_object, model_file)
            
            # Save metadata
            metadata_file = model_dir / "metadata.json"
            if metadata:
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2, default=str)
            
            # Calculate model size
            model_size_mb = model_file.stat().st_size / (1024 * 1024)
            
            # Create model version record
            model_version = ModelVersion(
                model_name=model_name,
                version=version,
                model_type=model_type,
                status='training',
                train_auc=performance_metrics.get('train_auc'),
                val_auc=performance_metrics.get('val_auc'),
                test_auc=performance_metrics.get('test_auc'),
                train_f1=performance_metrics.get('train_f1'),
                val_f1=performance_metrics.get('val_f1'),
                test_f1=performance_metrics.get('test_f1'),
                accuracy=performance_metrics.get('accuracy'),
                precision=performance_metrics.get('precision'),
                recall=performance_metrics.get('recall'),
                feature_count=performance_metrics.get('feature_count'),
                training_samples=performance_metrics.get('training_samples'),
                training_duration=performance_metrics.get('training_duration'),
                model_size_mb=model_size_mb,
                model_path=str(model_file),
                metadata_path=str(metadata_file) if metadata else None,
                description=metadata.get('description') if metadata else None,
                hyperparameters=json.dumps(metadata.get('hyperparameters', {})) if metadata else '{}',
                feature_importance=json.dumps(metadata.get('feature_importance', [])) if metadata else '[]'
            )
            
            session.add(model_version)
            session.commit()
            
            model_id = str(model_version.id)
            
            logger.info(f"Model registered: {model_name} v{version} (ID: {model_id})")
            
            return model_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to register model: {e}")
            raise
        finally:
            session.close()
    
    def get_active_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the currently active model version.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model version information or None if no active model
        """
        session = self.SessionLocal()
        
        try:
            model_version = session.query(ModelVersion).filter(
                ModelVersion.model_name == model_name,
                ModelVersion.status == 'active'
            ).order_by(ModelVersion.deployed_at.desc()).first()
            
            if model_version:
                return self._model_version_to_dict(model_version)
            else:
                return None
                
        finally:
            session.close()
    
    def deploy_model(
        self, 
        model_version_id: str,
        environment: str = 'production',
        deployed_by: str = 'system'
    ) -> bool:
        """
        Deploy a model version to the specified environment.
        
        Args:
            model_version_id: Model version ID to deploy
            environment: Deployment environment
            deployed_by: Who is deploying the model
            
        Returns:
            True if deployment successful, False otherwise
        """
        session = self.SessionLocal()
        
        try:
            # Get model version
            model_version = session.query(ModelVersion).filter(
                ModelVersion.id == model_version_id
            ).first()
            
            if not model_version:
                logger.error(f"Model version {model_version_id} not found")
                return False
            
            # Deprecate any existing active models for this model name
            session.query(ModelVersion).filter(
                ModelVersion.model_name == model_version.model_name,
                ModelVersion.status == 'active'
            ).update({
                'status': 'deprecated',
                'deprecated_at': datetime.utcnow()
            })
            
            # Set new model as active
            model_version.status = 'active'
            model_version.deployed_at = datetime.utcnow()
            
            # Create deployment record
            deployment = ModelDeployment(
                model_version_id=model_version_id,
                deployment_environment=environment,
                deployed_by=deployed_by,
                deployment_status='deployed'
            )
            
            session.add(deployment)
            session.commit()
            
            logger.info(f"Model deployed: {model_version.model_name} v{model_version.version} to {environment}")
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to deploy model: {e}")
            return False
        finally:
            session.close()
    
    def record_drift_analysis(
        self,
        model_version_id: str,
        analysis_type: str,
        drift_results: Dict[str, Any],
        action_taken: str = 'none'
    ) -> str:
        """
        Record drift analysis results.
        
        Args:
            model_version_id: Model version ID
            analysis_type: Type of drift analysis
            drift_results: Drift analysis results
            action_taken: Action taken based on drift results
            
        Returns:
            Drift analysis ID
        """
        session = self.SessionLocal()
        
        try:
            # Create drift analysis record
            drift_analysis = DriftAnalysis(
                model_version_id=model_version_id,
                analysis_type=analysis_type,
                drift_score=drift_results.get('max_psi', 0),
                drifted_features_count=drift_results.get('drifted_count', 0),
                total_features=drift_results.get('total_features', 0),
                max_psi=drift_results.get('max_psi', 0),
                drift_results=json.dumps(drift_results, default=str),
                feature_drift_details=json.dumps(drift_results.get('detailed_psi', {}), default=str),
                action_taken=action_taken,
                action_timestamp=datetime.utcnow() if action_taken != 'none' else None
            )
            
            session.add(drift_analysis)
            
            # Update model version drift status
            if drift_results.get('drifted_count', 0) > 0:
                session.query(ModelVersion).filter(
                    ModelVersion.id == model_version_id
                ).update({
                    'drift_score': drift_results.get('max_psi', 0),
                    'last_drift_check': datetime.utcnow(),
                    'drift_status': 'detected'
                })
            else:
                session.query(ModelVersion).filter(
                    ModelVersion.id == model_version_id
                ).update({
                    'drift_score': drift_results.get('max_psi', 0),
                    'last_drift_check': datetime.utcnow(),
                    'drift_status': 'stable'
                })
            
            session.commit()
            
            analysis_id = str(drift_analysis.id)
            
            logger.info(f"Drift analysis recorded: {analysis_type} for model {model_version_id}")
            
            return analysis_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to record drift analysis: {e}")
            raise
        finally:
            session.close()
    
    def get_model_history(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Get the complete history of a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            List of model version dictionaries
        """
        session = self.SessionLocal()
        
        try:
            model_versions = session.query(ModelVersion).filter(
                ModelVersion.model_name == model_name
            ).order_by(ModelVersion.created_at.desc()).all()
            
            return [self._model_version_to_dict(mv) for mv in model_versions]
            
        finally:
            session.close()
    
    def get_drift_history(
        self, 
        model_version_id: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get drift analysis history.
        
        Args:
            model_version_id: Specific model version ID (optional)
            days: Number of days to look back
            
        Returns:
            List of drift analysis records
        """
        session = self.SessionLocal()
        
        try:
            query = session.query(DriftAnalysis).filter(
                DriftAnalysis.analysis_date >= datetime.utcnow() - timedelta(days=days)
            )
            
            if model_version_id:
                query = query.filter(DriftAnalysis.model_version_id == model_version_id)
            
            drift_analyses = query.order_by(DriftAnalysis.analysis_date.desc()).all()
            
            results = []
            for analysis in drift_analyses:
                result = {
                    'id': str(analysis.id),
                    'model_version_id': str(analysis.model_version_id),
                    'analysis_date': analysis.analysis_date.isoformat(),
                    'analysis_type': analysis.analysis_type,
                    'drift_score': analysis.drift_score,
                    'drifted_features_count': analysis.drifted_features_count,
                    'total_features': analysis.total_features,
                    'max_psi': analysis.max_psi,
                    'action_taken': analysis.action_taken,
                    'action_timestamp': analysis.action_timestamp.isoformat() if analysis.action_timestamp else None
                }
                
                # Parse detailed results if available
                if analysis.drift_results:
                    try:
                        result['drift_results'] = json.loads(analysis.drift_results)
                    except json.JSONDecodeError:
                        result['drift_results'] = {}
                
                results.append(result)
            
            return results
            
        finally:
            session.close()
    
    def get_performance_comparison(self, model_name: str) -> pd.DataFrame:
        """
        Get performance comparison across model versions.
        
        Args:
            model_name: Name of the model
            
        Returns:
            DataFrame with performance metrics comparison
        """
        session = self.SessionLocal()
        
        try:
            model_versions = session.query(ModelVersion).filter(
                ModelVersion.model_name == model_name
            ).order_by(ModelVersion.created_at).all()
            
            data = []
            for mv in model_versions:
                data.append({
                    'version': mv.version,
                    'created_at': mv.created_at,
                    'status': mv.status,
                    'train_auc': mv.train_auc,
                    'val_auc': mv.val_auc,
                    'test_auc': mv.test_auc,
                    'train_f1': mv.train_f1,
                    'val_f1': mv.val_f1,
                    'test_f1': mv.test_f1,
                    'accuracy': mv.accuracy,
                    'precision': mv.precision,
                    'recall': mv.recall,
                    'drift_score': mv.drift_score,
                    'drift_status': mv.drift_status
                })
            
            return pd.DataFrame(data)
            
        finally:
            session.close()
    
    def get_models_needing_attention(self, drift_threshold: float = 0.2) -> List[Dict[str, Any]]:
        """
        Get models that need attention due to drift or other issues.
        
        Args:
            drift_threshold: PSI threshold for considering drift
            
        Returns:
            List of models needing attention
        """
        session = self.SessionLocal()
        
        try:
            # Get active models with high drift
            models = session.query(ModelVersion).filter(
                ModelVersion.status == 'active',
                ModelVersion.drift_score > drift_threshold
            ).all()
            
            results = []
            for model in models:
                # Get recent drift analyses
                recent_drift = session.query(DriftAnalysis).filter(
                    DriftAnalysis.model_version_id == model.id,
                    DriftAnalysis.analysis_date >= datetime.utcnow() - timedelta(days=7)
                ).order_by(DriftAnalysis.analysis_date.desc()).first()
                
                model_info = self._model_version_to_dict(model)
                if recent_drift:
                    model_info['recent_drift_analysis'] = {
                        'analysis_date': recent_drift.analysis_date.isoformat(),
                        'drift_score': recent_drift.drift_score,
                        'drifted_features_count': recent_drift.drifted_features_count,
                        'action_taken': recent_drift.action_taken
                    }
                
                results.append(model_info)
            
            return results
            
        finally:
            session.close()
    
    def load_model(self, model_version_id: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Load a model from the registry.
        
        Args:
            model_version_id: Model version ID
            
        Returns:
            Tuple of (model_object, metadata)
        """
        session = self.SessionLocal()
        
        try:
            model_version = session.query(ModelVersion).filter(
                ModelVersion.id == model_version_id
            ).first()
            
            if not model_version:
                raise ValueError(f"Model version {model_version_id} not found")
            
            # Load model from file
            model_object = joblib.load(model_version.model_path)
            
            # Load metadata
            metadata = {}
            if model_version.metadata_path and Path(model_version.metadata_path).exists():
                with open(model_version.metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            return model_object, metadata
            
        finally:
            session.close()
    
    def rollback_model(self, model_name: str, target_version: str) -> bool:
        """
        Rollback to a specific model version.
        
        Args:
            model_name: Name of the model
            target_version: Target version to rollback to
            
        Returns:
            True if rollback successful, False otherwise
        """
        session = self.SessionLocal()
        
        try:
            # Get target model version
            target_model = session.query(ModelVersion).filter(
                ModelVersion.model_name == model_name,
                ModelVersion.version == target_version
            ).first()
            
            if not target_model:
                logger.error(f"Target model version {target_version} not found")
                return False
            
            # Deprecate current active model
            current_active = session.query(ModelVersion).filter(
                ModelVersion.model_name == model_name,
                ModelVersion.status == 'active'
            ).first()
            
            if current_active:
                current_active.status = 'deprecated'
                current_active.deprecated_at = datetime.utcnow()
            
            # Activate target model
            target_model.status = 'active'
            target_model.deployed_at = datetime.utcnow()
            
            # Record rollback in deployment
            deployment = ModelDeployment(
                model_version_id=str(target_model.id),
                deployment_environment='production',
                deployment_status='rolled_back',
                deployment_notes=f"Rollback from version {current_active.version if current_active else 'unknown'} to {target_version}"
            )
            
            session.add(deployment)
            session.commit()
            
            logger.info(f"Model rolled back: {model_name} to version {target_version}")
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to rollback model: {e}")
            return False
        finally:
            session.close()
    
    def _model_version_to_dict(self, model_version: ModelVersion) -> Dict[str, Any]:
        """Convert ModelVersion object to dictionary."""
        return {
            'id': str(model_version.id),
            'model_name': model_version.model_name,
            'version': model_version.version,
            'model_type': model_version.model_type,
            'status': model_version.status,
            'train_auc': model_version.train_auc,
            'val_auc': model_version.val_auc,
            'test_auc': model_version.test_auc,
            'train_f1': model_version.train_f1,
            'val_f1': model_version.val_f1,
            'test_f1': model_version.test_f1,
            'accuracy': model_version.accuracy,
            'precision': model_version.precision,
            'recall': model_version.recall,
            'feature_count': model_version.feature_count,
            'training_samples': model_version.training_samples,
            'training_duration': model_version.training_duration,
            'model_size_mb': model_version.model_size_mb,
            'created_at': model_version.created_at.isoformat(),
            'deployed_at': model_version.deployed_at.isoformat() if model_version.deployed_at else None,
            'deprecated_at': model_version.deprecated_at.isoformat() if model_version.deprecated_at else None,
            'description': model_version.description,
            'drift_score': model_version.drift_score,
            'last_drift_check': model_version.last_drift_check.isoformat() if model_version.last_drift_check else None,
            'drift_status': model_version.drift_status
        }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        session = self.SessionLocal()
        
        try:
            total_models = session.query(ModelVersion).count()
            active_models = session.query(ModelVersion).filter(ModelVersion.status == 'active').count()
            deprecated_models = session.query(ModelVersion).filter(ModelVersion.status == 'deprecated').count()
            
            # Models with drift
            drifted_models = session.query(ModelVersion).filter(
                ModelVersion.drift_status == 'detected'
            ).count()
            
            # Recent drift analyses
            recent_drift = session.query(DriftAnalysis).filter(
                DriftAnalysis.analysis_date >= datetime.utcnow() - timedelta(days=7)
            ).count()
            
            return {
                'total_models': total_models,
                'active_models': active_models,
                'deprecated_models': deprecated_models,
                'drifted_models': drifted_models,
                'recent_drift_analyses': recent_drift,
                'registry_size_mb': self._get_registry_size()
            }
            
        finally:
            session.close()
    
    def _get_registry_size(self) -> float:
        """Calculate total size of model registry in MB."""
        total_size = 0
        
        for model_dir in self.model_storage_path.iterdir():
            if model_dir.is_dir():
                for file_path in model_dir.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
        
        return total_size / (1024 * 1024)  # Convert to MB
