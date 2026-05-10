"""
Slack Alerting System for Model Drift and Retraining Notifications

This module provides comprehensive Slack integration for sending alerts about
model drift, retraining events, and performance changes.
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class SlackNotifier:
    """
    Slack notification system for model monitoring alerts.
    
    This class provides methods to send formatted alerts to Slack channels
    about model drift, retraining events, and performance changes.
    """
    
    def __init__(
        self, 
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        channel: str = "#model-alerts",
        username: str = "ML Monitor Bot"
    ):
        """
        Initialize the Slack notifier.
        
        Args:
            webhook_url: Slack webhook URL for incoming webhooks
            bot_token: Slack bot token for chat.postMessage API
            channel: Default channel to send messages to
            username: Username for the bot
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel = channel
        self.username = username
        
        if not webhook_url and not bot_token:
            logger.warning("No webhook_url or bot_token provided. Slack notifications disabled.")
    
    def send_drift_alert(
        self,
        model_name: str,
        model_version: str,
        drift_results: Dict[str, Any],
        action_taken: str = "none"
    ) -> bool:
        """
        Send alert about detected model drift.
        
        Args:
            model_name: Name of the model
            model_version: Version of the model
            drift_results: Drift analysis results
            action_taken: Action taken based on drift
            
        Returns:
            True if alert sent successfully, False otherwise
        """
        logger.info(f"Sending drift alert for {model_name} v{model_version}")
        
        drifted_features = drift_results.get('drifted_features', [])
        max_psi = drift_results.get('max_psi', 0)
        drifted_count = drift_results.get('drifted_count', 0)
        
        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Model Drift Detected",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Model:*\n{model_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Version:*\n{model_version}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Max PSI:*\n{max_psi:.3f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Drifted Features:*\n{drifted_count}"
                    }
                ]
            }
        ]
        
        # Add drifted features if any
        if drifted_features:
            features_text = "\n".join([f"• {feature}" for feature in drifted_features[:10]])
            if len(drifted_features) > 10:
                features_text += f"\n• ... and {len(drifted_features) - 10} more"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Drifted Features:*\n{features_text}"
                }
            })
        
        # Add action taken
        action_emoji = {"none": "⏳", "retrained": "🔄", "deprecated": "🗑️", "monitored": "👁️"}
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Action Taken:*\n{action_emoji.get(action_taken, '❓')} {action_taken.title()}"
            }
        })
        
        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })
        
        return self._send_message(blocks)
    
    def send_retraining_alert(
        self,
        model_name: str,
        old_version: str,
        new_version: str,
        old_metrics: Dict[str, float],
        new_metrics: Dict[str, float],
        drift_reason: str = "Model drift detected"
    ) -> bool:
        """
        Send alert about model retraining.
        
        Args:
            model_name: Name of the model
            old_version: Previous model version
            new_version: New model version
            old_metrics: Performance metrics of old model
            new_metrics: Performance metrics of new model
            drift_reason: Reason for retraining
            
        Returns:
            True if alert sent successfully, False otherwise
        """
        logger.info(f"Sending retraining alert for {model_name}: {old_version} → {new_version}")
        
        # Calculate performance changes
        auc_change = new_metrics.get('test_auc', 0) - old_metrics.get('test_auc', 0)
        f1_change = new_metrics.get('test_f1', 0) - old_metrics.get('test_f1', 0)
        
        # Determine change indicators
        auc_indicator = "📈" if auc_change > 0 else "📉"
        f1_indicator = "📈" if f1_change > 0 else "📉"
        
        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 Model Retrained",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Model:*\n{model_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Retraining Reason:*\n{drift_reason}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Version Update*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Previous:*\nv{old_version}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*New:*\nv{new_version}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Performance Comparison*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*AUC:*\n{old_metrics.get('test_auc', 0):.3f} → {new_metrics.get('test_auc', 0):.3f}\n{auc_indicator} {auc_change:+.3f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*F1-Score:*\n{old_metrics.get('test_f1', 0):.3f} → {new_metrics.get('test_f1', 0):.3f}\n{f1_indicator} {f1_change:+.3f}"
                    }
                ]
            }
        ]
        
        # Add improvement/degradation assessment
        if auc_change > 0.01 and f1_change > 0.01:
            assessment = "✅ Significant improvement in both metrics"
        elif auc_change > 0.01 or f1_change > 0.01:
            assessment = "⚠️ Partial improvement"
        elif auc_change < -0.01 or f1_change < -0.01:
            assessment = "❌ Performance degradation"
        else:
            assessment = "➡️ Minimal change in performance"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Assessment:*\n{assessment}"
            }
        })
        
        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })
        
        return self._send_message(blocks)
    
    def send_performance_alert(
        self,
        model_name: str,
        model_version: str,
        current_metrics: Dict[str, float],
        baseline_metrics: Dict[str, float],
        threshold_violations: List[str]
    ) -> bool:
        """
        Send alert about performance degradation.
        
        Args:
            model_name: Name of the model
            model_version: Version of the model
            current_metrics: Current performance metrics
            baseline_metrics: Baseline performance metrics
            threshold_violations: List of violated thresholds
            
        Returns:
            True if alert sent successfully, False otherwise
        """
        logger.info(f"Sending performance alert for {model_name} v{model_version}")
        
        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ Performance Degradation",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Model:*\n{model_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Version:*\n{model_version}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Threshold Violations*"
                }
            }
        ]
        
        # Add threshold violations
        violations_text = "\n".join([f"• {violation}" for violation in threshold_violations])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": violations_text
            }
        })
        
        # Add performance comparison
        blocks.append({
            "type": "divider"
        })
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Performance Comparison*"
            }
        })
        
        # Compare key metrics
        for metric in ['test_auc', 'test_f1', 'accuracy', 'precision', 'recall']:
            if metric in current_metrics and metric in baseline_metrics:
                current = current_metrics[metric]
                baseline = baseline_metrics[metric]
                change = current - baseline
                indicator = "📉" if change < 0 else "📈"
                
                blocks.append({
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*{metric.replace('_', ' ').title()}:*\n{baseline:.3f} → {current:.3f}\n{indicator} {change:+.3f}"
                        }
                    ]
                })
        
        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })
        
        return self._send_message(blocks)
    
    def send_weekly_report(
        self,
        report_data: Dict[str, Any]
    ) -> bool:
        """
        Send weekly monitoring report.
        
        Args:
            report_data: Weekly report data
            
        Returns:
            True if report sent successfully, False otherwise
        """
        logger.info("Sending weekly monitoring report")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Weekly Model Monitoring Report",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Week of:* {datetime.now().strftime('%Y-%m-%d')}"
                }
            }
        ]
        
        # Add summary statistics
        summary = report_data.get('summary', {})
        if summary:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Summary Statistics*"
                }
            })
            
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Models:*\n{summary.get('total_models', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Active Models:*\n{summary.get('active_models', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Models with Drift:*\n{summary.get('drifted_models', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Retrained Models:*\n{summary.get('retrained_models', 0)}"
                    }
                ]
            })
        
        # Add model-specific details
        models_data = report_data.get('models', [])
        if models_data:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Model Details*"
                }
            })
            
            for model in models_data[:5]:  # Limit to top 5 models
                status_emoji = "✅" if model.get('drift_status') == 'stable' else "⚠️"
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *{model.get('model_name', 'Unknown')}* v{model.get('version', 'N/A')}\n"
                               f"Drift Score: {model.get('drift_score', 0):.3f} | "
                               f"AUC: {model.get('test_auc', 0):.3f}"
                    }
                })
        
        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })
        
        return self._send_message(blocks)
    
    def send_drift_plot(
        self,
        model_name: str,
        plot_path: str,
        caption: str = "Drift Analysis Plot"
    ) -> bool:
        """
        Send a drift analysis plot to Slack.
        
        Args:
            model_name: Name of the model
            plot_path: Path to the plot image
            caption: Caption for the plot
            
        Returns:
            True if plot sent successfully, False otherwise
        """
        try:
            # Read and encode the image
            with open(plot_path, 'rb') as f:
                image_data = f.read()
            
            # Upload image to Slack
            if self.bot_token:
                return self._upload_image(image_data, model_name, caption)
            else:
                logger.warning("Bot token required for image uploads")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send drift plot: {e}")
            return False
    
    def _send_message(self, blocks: List[Dict[str, Any]]) -> bool:
        """Send message to Slack using webhook."""
        if not self.webhook_url:
            logger.warning("No webhook URL configured. Skipping Slack notification.")
            return False
        
        payload = {
            "username": self.username,
            "channel": self.channel,
            "blocks": blocks
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Slack notification sent successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def _upload_image(self, image_data: bytes, model_name: str, caption: str) -> bool:
        """Upload image to Slack using bot token."""
        if not self.bot_token:
            return False
        
        try:
            # Upload image
            upload_url = "https://slack.com/api/files.upload"
            headers = {
                "Authorization": f"Bearer {self.bot_token}"
            }
            
            files = {
                'file': image_data,
                'channels': (None, self.channel),
                'initial_comment': (None, f"📊 {model_name}: {caption}")
            }
            
            response = requests.post(upload_url, headers=headers, files=files, timeout=30)
            response.raise_for_status()
            
            logger.info("Slack image uploaded successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload image to Slack: {e}")
            return False
    
    def create_drift_plot(
        self,
        drift_data: Dict[str, Any],
        save_path: str = "reports/drift_plot.png"
    ) -> str:
        """
        Create a drift analysis plot.
        
        Args:
            drift_data: Drift analysis data
            save_path: Path to save the plot
            
        Returns:
            Path to the saved plot
        """
        # Extract PSI scores
        psi_scores = drift_data.get('psi_scores', {})
        
        if not psi_scores:
            logger.warning("No PSI scores found in drift data")
            return ""
        
        # Create DataFrame for plotting
        df = pd.DataFrame(list(psi_scores.items()), columns=['Feature', 'PSI'])
        df = df.sort_values('PSI', ascending=True)
        
        # Create plot
        plt.figure(figsize=(12, 8))
        
        # Color code by PSI threshold
        colors = ['red' if psi > 0.2 else 'orange' if psi > 0.1 else 'green' for psi in df['PSI']]
        
        bars = plt.barh(df['Feature'], df['PSI'], color=colors, alpha=0.7)
        
        # Add threshold line
        plt.axvline(x=0.2, color='red', linestyle='--', alpha=0.8, label='Drift Threshold (0.2)')
        plt.axvline(x=0.1, color='orange', linestyle='--', alpha=0.6, label='Warning Threshold (0.1)')
        
        # Customize plot
        plt.xlabel('Population Stability Index (PSI)', fontsize=12)
        plt.title('Model Drift Analysis - PSI Scores', fontsize=14, fontweight='bold')
        plt.legend()
        plt.grid(axis='x', alpha=0.3)
        
        # Add value labels on bars
        for i, (bar, psi) in enumerate(zip(bars, df['PSI'])):
            plt.text(psi + 0.01, bar.get_y() + bar.get_height()/2, 
                    f'{psi:.3f}', va='center', fontsize=10)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = Path(save_path)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Drift plot saved to {plot_path}")
        
        return str(plot_path)
    
    def test_connection(self) -> bool:
        """Test Slack connection."""
        test_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🧪 Slack connection test successful!"
                }
            }
        ]
        
        return self._send_message(test_blocks)
