"""
Model Drift Detection Module

This module provides comprehensive drift detection capabilities including
Population Stability Index (PSI) calculation, Evidently-based drift analysis,
and SHAP-based feature importance comparison over time.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import shap
from sklearn.preprocessing import KBinsDiscretizer

# Evidently imports
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset, RegressionPerformancePreset
from evidently.dashboard import Dashboard
from evidently.pipeline.column_mapping import ColumnMapping

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Comprehensive drift detection system for credit default models.
    
    This class provides multiple methods for detecting model and data drift
    including PSI calculation, statistical tests, and visualization tools.
    """
    
    def __init__(self, psi_threshold: float = 0.2, random_state: int = 42):
        """
        Initialize the drift detector.
        
        Args:
            psi_threshold: Threshold for PSI to consider significant drift
            random_state: Random seed for reproducibility
        """
        self.psi_threshold = psi_threshold
        self.random_state = random_state
        np.random.seed(random_state)
        self.feature_names = None
        self.reference_data = None
        self.drift_history = []
        
    def calculate_psi(
        self, 
        reference_data: pd.DataFrame, 
        current_data: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
        bins: int = 10
    ) -> Dict[str, Any]:
        """
        Calculate Population Stability Index (PSI) for features.
        
        Args:
            reference_data: Reference/training data
            current_data: Current/production data
            feature_columns: List of features to analyze (if None, use all)
            bins: Number of bins for PSI calculation
            
        Returns:
            Dictionary containing PSI results for each feature
        """
        logger.info(f"Calculating PSI for {len(feature_columns) if feature_columns else len(reference_data.columns)} features")
        
        if feature_columns is None:
            feature_columns = reference_data.columns.tolist()
        
        self.feature_names = feature_columns
        psi_results = {}
        detailed_psi = {}
        
        for feature in feature_columns:
            if feature not in reference_data.columns or feature not in current_data.columns:
                logger.warning(f"Feature {feature} not found in data")
                continue
            
            ref_values = reference_data[feature].dropna()
            cur_values = current_data[feature].dropna()
            
            if len(ref_values) == 0 or len(cur_values) == 0:
                logger.warning(f"No valid data for feature {feature}")
                continue
            
            # Calculate PSI
            psi_score, psi_details = self._calculate_single_psi(
                ref_values, cur_values, feature, bins
            )
            
            psi_results[feature] = psi_score
            detailed_psi[feature] = psi_details
        
        # Identify drifted features
        drifted_features = [
            feature for feature, psi in psi_results.items() 
            if psi > self.psi_threshold
        ]
        
        # Store reference data for future comparisons
        self.reference_data = reference_data[feature_columns].copy()
        
        results = {
            'psi_scores': psi_results,
            'detailed_psi': detailed_psi,
            'drifted_features': drifted_features,
            'max_psi': max(psi_results.values()) if psi_results else 0,
            'drifted_count': len(drifted_features),
            'total_features': len(psi_results),
            'threshold': self.psi_threshold,
            'calculation_time': datetime.now().isoformat()
        }
        
        # Add to drift history
        self.drift_history.append({
            'timestamp': datetime.now().isoformat(),
            'psi_results': results
        })
        
        logger.info(f"PSI calculation completed. {len(drifted_features)} features drifted above threshold {self.psi_threshold}")
        
        return results
    
    def _calculate_single_psi(
        self, 
        reference_values: pd.Series, 
        current_values: pd.Series,
        feature_name: str,
        bins: int
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate PSI for a single feature."""
        
        # Determine bin edges based on reference data
        if reference_values.dtype in ['int64', 'float64']:
            # Numerical feature
            discretizer = KBinsDiscretizer(n_bins=bins, encode='ordinal', strategy='quantile')
            discretizer.fit(reference_values.values.reshape(-1, 1))
            
            ref_binned = discretizer.transform(reference_values.values.reshape(-1, 1)).flatten()
            cur_binned = discretizer.transform(current_values.values.reshape(-1, 1)).flatten()
            
            # Get bin edges for reporting
            bin_edges = discretizer.bin_edges_[0].tolist()
            
        else:
            # Categorical feature
            unique_values = list(set(reference_values.unique()) | set(current_values.unique()))
            value_to_bin = {val: i for i, val in enumerate(unique_values)}
            
            ref_binned = reference_values.map(value_to_bin).fillna(-1)
            cur_binned = current_values.map(value_to_bin).fillna(-1)
            
            bin_edges = unique_values
        
        # Calculate distributions
        ref_dist, _ = np.histogram(ref_binned, bins=len(bin_edges) + 1, range=(-1, len(bin_edges)))
        cur_dist, _ = np.histogram(cur_binned, bins=len(bin_edges) + 1, range=(-1, len(bin_edges)))
        
        # Convert to percentages
        ref_pct = ref_dist / len(reference_values)
        cur_pct = cur_dist / len(current_values)
        
        # Calculate PSI
        psi_components = []
        for i in range(len(ref_pct)):
            if ref_pct[i] == 0:
                psi_component = 0
            else:
                psi_component = (cur_pct[i] - ref_pct[i]) * np.log(cur_pct[i] / ref_pct[i])
            psi_components.append(psi_component)
        
        psi_score = sum(psi_components)
        
        # Create detailed breakdown
        psi_details = {
            'psi_score': psi_score,
            'reference_distribution': ref_pct.tolist(),
            'current_distribution': cur_pct.tolist(),
            'psi_components': psi_components,
            'bin_edges': bin_edges,
            'reference_count': len(reference_values),
            'current_count': len(current_values)
        }
        
        return psi_score, psi_details
    
    def analyze_shap_drift(
        self,
        reference_model: Any,
        current_model: Any,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        sample_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Analyze drift in SHAP feature importance between reference and current models.
        
        Args:
            reference_model: Reference/trained model
            current_model: Current model (can be same model with new data)
            reference_data: Reference data
            current_data: Current data
            sample_size: Number of samples to analyze
            
        Returns:
            Dictionary containing SHAP drift analysis results
        """
        logger.info("Analyzing SHAP feature importance drift")
        
        # Sample data if needed
        if len(reference_data) > sample_size:
            ref_sample = reference_data.sample(n=sample_size, random_state=self.random_state)
        else:
            ref_sample = reference_data
        
        if len(current_data) > sample_size:
            cur_sample = current_data.sample(n=sample_size, random_state=self.random_state)
        else:
            cur_sample = current_data
        
        # Generate SHAP values for reference model
        ref_shap_values, ref_feature_importance = self._generate_shap_analysis(
            reference_model, ref_sample
        )
        
        # Generate SHAP values for current model
        cur_shap_values, cur_feature_importance = self._generate_shap_analysis(
            current_model, cur_sample
        )
        
        # Compare feature importance
        importance_comparison = self._compare_feature_importance(
            ref_feature_importance, cur_feature_importance
        )
        
        # Calculate SHAP value drift
        shap_drift = self._calculate_shap_value_drift(ref_shap_values, cur_shap_values)
        
        results = {
            'reference_importance': ref_feature_importance.to_dict('records'),
            'current_importance': cur_feature_importance.to_dict('records'),
            'importance_comparison': importance_comparison,
            'shap_drift_metrics': shap_drift,
            'sample_size': sample_size,
            'analysis_time': datetime.now().isoformat()
        }
        
        # Save SHAP comparison plots
        self._save_shap_drift_plots(ref_feature_importance, cur_feature_importance)
        
        logger.info("SHAP drift analysis completed")
        
        return results
    
    def _generate_shap_analysis(
        self, 
        model: Any, 
        data: pd.DataFrame
    ) -> Tuple[np.ndarray, pd.DataFrame]:
        """Generate SHAP values and feature importance for a model."""
        
        # Get the model from pipeline if it's a scikit-learn pipeline
        if hasattr(model, 'named_steps'):
            actual_model = model.named_steps['model']
            scaler = model.named_steps.get('scaler')
            
            # Scale data if scaler exists
            if scaler:
                data_scaled = scaler.transform(data)
            else:
                data_scaled = data
        else:
            actual_model = model
            data_scaled = data
        
        # Create SHAP explainer
        if hasattr(actual_model, 'feature_importances_'):
            # Tree-based models
            explainer = shap.TreeExplainer(actual_model)
        elif hasattr(actual_model, 'coef_'):
            # Linear models
            explainer = shap.LinearExplainer(actual_model, data_scaled)
        else:
            # Use KernelExplainer as fallback
            explainer = shap.KernelExplainer(actual_model.predict, data_scaled)
        
        # Calculate SHAP values
        shap_values = explainer.shap_values(data_scaled)
        
        # For binary classification, get SHAP values for positive class
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        # Calculate feature importance
        feature_importance = np.abs(shap_values).mean(axis=0)
        importance_df = pd.DataFrame({
            'feature': data.columns,
            'importance': feature_importance
        }).sort_values('importance', ascending=False)
        
        return shap_values, importance_df
    
    def _compare_feature_importance(
        self, 
        ref_importance: pd.DataFrame, 
        cur_importance: pd.DataFrame
    ) -> Dict[str, Any]:
        """Compare feature importance between reference and current models."""
        
        # Merge importance DataFrames
        comparison = ref_importance.merge(
            cur_importance, on='feature', suffixes=('_reference', '_current')
        )
        
        # Calculate change in importance
        comparison['importance_change'] = comparison['importance_current'] - comparison['importance_reference']
        comparison['importance_change_pct'] = (
            comparison['importance_change'] / comparison['importance_reference'] * 100
        )
        
        # Identify most changed features
        comparison['abs_change'] = comparison['importance_change'].abs()
        most_changed = comparison.nlargest(10, 'abs_change')
        
        # Calculate correlation between importance rankings
        rank_correlation = comparison['importance_reference'].corr(comparison['importance_current'])
        
        return {
            'comparison_table': comparison.to_dict('records'),
            'most_changed_features': most_changed.to_dict('records'),
            'importance_correlation': rank_correlation,
            'top_10_reference': ref_importance.head(10).to_dict('records'),
            'top_10_current': cur_importance.head(10).to_dict('records')
        }
    
    def _calculate_shap_value_drift(
        self, 
        ref_shap_values: np.ndarray, 
        cur_shap_values: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate drift metrics for SHAP values."""
        
        # Calculate statistical tests for each feature
        drift_metrics = {}
        
        for i in range(ref_shap_values.shape[1]):
            ref_values = ref_shap_values[:, i]
            cur_values = cur_shap_values[:, i]
            
            # Kolmogorov-Smirnov test
            ks_statistic, ks_p_value = stats.ks_2samp(ref_values, cur_values)
            
            # Mann-Whitney U test
            mw_statistic, mw_p_value = stats.mannwhitneyu(ref_values, cur_values, alternative='two-sided')
            
            # Calculate distribution statistics
            ref_mean, ref_std = np.mean(ref_values), np.std(ref_values)
            cur_mean, cur_std = np.mean(cur_values), np.std(cur_values)
            
            drift_metrics[f'feature_{i}'] = {
                'ks_statistic': ks_statistic,
                'ks_p_value': ks_p_value,
                'mw_statistic': mw_statistic,
                'mw_p_value': mw_p_value,
                'ref_mean': ref_mean,
                'ref_std': ref_std,
                'cur_mean': cur_mean,
                'cur_std': cur_std,
                'mean_diff': cur_mean - ref_mean,
                'std_diff': cur_std - ref_std
            }
        
        # Overall drift summary
        significant_drift_features = sum(
            1 for metrics in drift_metrics.values() 
            if metrics['ks_p_value'] < 0.05
        )
        
        return {
            'feature_drift_metrics': drift_metrics,
            'significant_drift_count': significant_drift_features,
            'total_features': len(drift_metrics),
            'drift_percentage': significant_drift_features / len(drift_metrics) * 100
        }
    
    def create_evidently_report(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        reference_target: Optional[pd.Series] = None,
        current_target: Optional[pd.Series] = None,
        report_path: str = "reports/drift_report.html"
    ) -> Dict[str, Any]:
        """
        Create comprehensive drift report using Evidently.
        
        Args:
            reference_data: Reference/training data
            current_data: Current/production data
            reference_target: Reference target variable
            current_target: Current target variable
            report_path: Path to save the HTML report
            
        Returns:
            Dictionary containing report summary
        """
        logger.info("Creating Evidently drift report")
        
        # Create column mapping
        column_mapping = ColumnMapping()
        
        if reference_target is not None and current_target is not None:
            column_mapping.target = 'target'
            
            # Add targets to dataframes
            ref_data = reference_data.copy()
            ref_data['target'] = reference_target
            
            cur_data = current_data.copy()
            cur_data['target'] = current_target
            
            # Use target drift preset
            data_drift_report = Report(metrics=[TargetDriftPreset()])
        else:
            # Use only data drift preset
            ref_data = reference_data
            cur_data = current_data
            
            data_drift_report = Report(metrics=[DataDriftPreset()])
        
        # Generate report
        data_drift_report.run(
            reference_data=ref_data,
            current_data=cur_data,
            column_mapping=column_mapping
        )
        
        # Save report
        report_path_obj = Path(report_path)
        report_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        data_drift_report.save_html(str(report_path_obj))
        
        # Extract summary metrics
        report_summary = self._extract_evidently_summary(data_drift_report)
        
        logger.info(f"Evidently report saved to {report_path}")
        
        return {
            'report_path': str(report_path_obj),
            'summary': report_summary,
            'generation_time': datetime.now().isoformat()
        }
    
    def _extract_evidently_summary(self, report: Report) -> Dict[str, Any]:
        """Extract summary metrics from Evidently report."""
        # This is a simplified extraction - in practice, you'd parse the actual report
        # For now, we'll return a placeholder structure
        
        summary = {
            'data_drift_detected': False,
            'target_drift_detected': False,
            'drifted_features_count': 0,
            'total_features': 0,
            'drift_score': 0.0
        }
        
        # In a real implementation, you would extract actual metrics from the report
        # For demonstration, we'll use the drift history if available
        
        if self.drift_history:
            latest_drift = self.drift_history[-1]['psi_results']
            summary['drifted_features_count'] = latest_drift['drifted_count']
            summary['total_features'] = latest_drift['total_features']
            summary['drift_score'] = latest_drift['max_psi']
            summary['data_drift_detected'] = latest_drift['drifted_count'] > 0
        
        return summary
    
    def analyze_temporal_drift(
        self,
        data_with_timestamps: pd.DataFrame,
        target_column: str = 'target',
        window_size: int = 30,
        min_samples: int = 100
    ) -> Dict[str, Any]:
        """
        Analyze drift over time using sliding windows.
        
        Args:
            data_with_timestamps: DataFrame with timestamp column and features
            target_column: Name of target column
            window_size: Size of sliding window in days
            min_samples: Minimum samples required for analysis
            
        Returns:
            Dictionary containing temporal drift analysis
        """
        logger.info(f"Analyzing temporal drift with window size {window_size} days")
        
        # Ensure we have timestamp column
        if 'timestamp' not in data_with_timestamps.columns:
            raise ValueError("Data must contain 'timestamp' column")
        
        # Sort by timestamp
        data_sorted = data_with_timestamps.sort_values('timestamp')
        
        # Get feature columns (exclude timestamp and target)
        feature_columns = [
            col for col in data_sorted.columns 
            if col not in ['timestamp', target_column]
        ]
        
        # Initialize results
        temporal_results = []
        reference_data = None
        
        # Analyze each window
        start_date = data_sorted['timestamp'].min()
        end_date = data_sorted['timestamp'].max()
        
        current_date = start_date
        window_num = 0
        
        while current_date <= end_date:
            window_end = current_date + timedelta(days=window_size)
            
            # Get data for current window
            window_data = data_sorted[
                (data_sorted['timestamp'] >= current_date) & 
                (data_sorted['timestamp'] < window_end)
            ]
            
            if len(window_data) >= min_samples:
                # First window becomes reference
                if reference_data is None:
                    reference_data = window_data[feature_columns].copy()
                    reference_target = window_data[target_column] if target_column in window_data.columns else None
                    logger.info(f"Reference window established: {current_date.date()} to {window_end.date()}")
                else:
                    # Calculate PSI against reference
                    current_features = window_data[feature_columns].copy()
                    current_target = window_data[target_column] if target_column in window_data.columns else None
                    
                    psi_results = self.calculate_psi(
                        reference_data, current_features, feature_columns
                    )
                    
                    # Store results
                    temporal_result = {
                        'window_start': current_date.isoformat(),
                        'window_end': window_end.isoformat(),
                        'window_num': window_num,
                        'sample_count': len(window_data),
                        'psi_results': psi_results
                    }
                    
                    temporal_results.append(temporal_result)
                    
                    logger.info(f"Window {window_num}: {len(window_data)} samples, "
                              f"{psi_results['drifted_count']} drifted features")
            
            current_date = window_end
            window_num += 1
        
        # Analyze drift trends
        drift_trends = self._analyze_drift_trends(temporal_results)
        
        return {
            'temporal_results': temporal_results,
            'drift_trends': drift_trends,
            'window_size': window_size,
            'total_windows': len(temporal_results),
            'analysis_time': datetime.now().isoformat()
        }
    
    def _analyze_drift_trends(self, temporal_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends in drift over time."""
        
        if not temporal_results:
            return {'message': 'No temporal results to analyze'}
        
        # Extract time series data
        dates = [pd.to_datetime(result['window_start']) for result in temporal_results]
        max_psi_values = [result['psi_results']['max_psi'] for result in temporal_results]
        drifted_counts = [result['psi_results']['drifted_count'] for result in temporal_results]
        
        # Calculate trend statistics
        psi_trend = np.polyfit(range(len(max_psi_values)), max_psi_values, 1)[0]
        drift_count_trend = np.polyfit(range(len(drifted_counts)), drifted_counts, 1)[0]
        
        # Identify peak drift periods
        peak_periods = []
        for i, result in enumerate(temporal_results):
            if result['psi_results']['max_psi'] > self.psi_threshold * 2:  # 2x threshold
                peak_periods.append({
                    'window_start': result['window_start'],
                    'window_end': result['window_end'],
                    'max_psi': result['psi_results']['max_psi'],
                    'drifted_features': result['psi_results']['drifted_count']
                })
        
        return {
            'dates': [date.isoformat() for date in dates],
            'max_psi_values': max_psi_values,
            'drifted_counts': drifted_counts,
            'psi_trend_slope': psi_trend,
            'drift_count_trend_slope': drift_count_trend,
            'peak_drift_periods': peak_periods,
            'average_psi': np.mean(max_psi_values),
            'max_psi': np.max(max_psi_values),
            'total_drifted_windows': sum(1 for count in drifted_counts if count > 0)
        }
    
    def _save_shap_drift_plots(
        self, 
        ref_importance: pd.DataFrame, 
        cur_importance: pd.DataFrame
    ):
        """Save SHAP drift comparison plots."""
        plots_dir = Path("reports/plots")
        plots_dir.mkdir(parents=True, exist_ok=True)
        
        # Feature importance comparison
        comparison = ref_importance.merge(
            cur_importance, on='feature', suffixes=('_reference', '_current')
        )
        
        # Plot top 10 features comparison
        top_features = comparison.nlargest(10, 'importance_reference')
        
        plt.figure(figsize=(12, 8))
        x = np.arange(len(top_features))
        width = 0.35
        
        plt.bar(x - width/2, top_features['importance_reference'], width, 
                label='Reference', alpha=0.7)
        plt.bar(x + width/2, top_features['importance_current'], width, 
                label='Current', alpha=0.7)
        
        plt.xlabel('Features')
        plt.ylabel('SHAP Importance')
        plt.title('Top 10 Feature Importance Comparison')
        plt.xticks(x, top_features['feature'], rotation=45, ha='right')
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_dir / "shap_importance_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Plot importance changes
        comparison['importance_change'] = comparison['importance_current'] - comparison['importance_reference']
        comparison['abs_change'] = comparison['importance_change'].abs()
        
        most_changed = comparison.nlargest(10, 'abs_change')
        
        plt.figure(figsize=(12, 8))
        colors = ['red' if x < 0 else 'green' for x in most_changed['importance_change']]
        plt.barh(range(len(most_changed)), most_changed['importance_change'], color=colors, alpha=0.7)
        plt.yticks(range(len(most_changed)), most_changed['feature'])
        plt.xlabel('Change in SHAP Importance')
        plt.title('Top 10 Features with Largest Importance Changes')
        plt.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        plt.tight_layout()
        plt.savefig(plots_dir / "shap_importance_changes.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("SHAP drift plots saved")
    
    def save_drift_report(
        self, 
        results: Dict[str, Any], 
        report_path: str = "reports/drift_analysis.json"
    ):
        """Save comprehensive drift analysis report."""
        report_path_obj = Path(report_path)
        report_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Add metadata
        results['metadata'] = {
            'psi_threshold': self.psi_threshold,
            'analysis_time': datetime.now().isoformat(),
            'drift_history_length': len(self.drift_history)
        }
        
        with open(report_path_obj, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Drift analysis report saved to {report_path}")
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of all drift analyses performed."""
        if not self.drift_history:
            return {'message': 'No drift history available'}
        
        latest_drift = self.drift_history[-1]['psi_results']
        
        summary = {
            'latest_analysis': {
                'timestamp': self.drift_history[-1]['timestamp'],
                'drifted_features': latest_drift['drifted_features'],
                'drifted_count': latest_drift['drifted_count'],
                'max_psi': latest_drift['max_psi'],
                'total_features': latest_drift['total_features']
            },
            'analysis_count': len(self.drift_history),
            'psi_threshold': self.psi_threshold,
            'feature_names': self.feature_names
        }
        
        return summary
