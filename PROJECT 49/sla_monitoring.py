"""
SLA Monitoring and Alerting System for Airflow DAGs
Comprehensive Service Level Agreement monitoring with real-time alerting
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import requests
import slack_sdk
from slack_sdk.webhook import WebhookClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


@dataclass
class SLAConfig:
    """Configuration for SLA monitoring"""
    max_duration_hours: float = 1.0
    warning_threshold_hours: float = 0.75
    critical_threshold_hours: float = 1.5
    check_interval_minutes: int = 5
    max_retries: int = 3
    retry_delay_minutes: int = 2
    
    # Alert channels
    slack_webhook_url: Optional[str] = None
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: List[str] = None
    
    # Monitoring settings
    enable_dag_level_sla: bool = True
    enable_task_level_sla: bool = True
    enable_runtime_monitoring: bool = True
    enable_failure_rate_monitoring: bool = True


@dataclass
class SLAViolation:
    """SLA violation event"""
    dag_id: str
    task_id: Optional[str]
    execution_date: str
    violation_type: str  # 'duration', 'failure_rate', 'runtime'
    actual_duration: Optional[float]
    sla_duration: float
    severity: str  # 'warning', 'critical', 'info'
    timestamp: datetime
    message: str
    metadata: Dict[str, Any]


@dataclass
class DAGMetrics:
    """Metrics for DAG performance"""
    dag_id: str
    execution_date: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration: Optional[float]
    state: str
    task_count: int
    completed_tasks: int
    failed_tasks: int
    running_tasks: int
    queued_tasks: int
    sla_met: bool
    sla_duration: float
    last_updated: datetime


class SLAMonitor:
    """
    Comprehensive SLA monitoring system for Airflow DAGs
    """
    
    def __init__(self, sla_config: SLAConfig, airflow_api_base: str = "http://localhost:8080/api/v1"):
        self.config = sla_config
        self.airflow_api_base = airflow_api_base
        self.violations = []
        self.dag_metrics = {}
        self.alert_callbacks = []
        
        # Initialize alert channels
        self.slack_client = None
        if sla_config.slack_webhook_url:
            self.slack_client = WebhookClient(sla_config.slack_webhook_url)
        
        logger.info("SLAMonitor initialized")
    
    def add_alert_callback(self, callback: Callable[[SLAViolation], None]):
        """Add custom alert callback"""
        self.alert_callbacks.append(callback)
    
    def get_dag_runs(self, dag_id: str, limit: int = 10) -> List[Dict]:
        """Get recent DAG runs from Airflow API"""
        try:
            url = f"{self.airflow_api_base}/dags/{dag_id}/dagRuns?limit={limit}&order_by=-execution_date"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json().get('dag_runs', [])
        except Exception as e:
            logger.error(f"Error getting DAG runs for {dag_id}: {e}")
            return []
    
    def get_task_instances(self, dag_id: str, execution_date: str) -> List[Dict]:
        """Get task instances for a specific DAG run"""
        try:
            url = f"{self.airflow_api_base}/dags/{dag_id}/dagRuns/{execution_date}/taskInstances"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json().get('task_instances', [])
        except Exception as e:
            logger.error(f"Error getting task instances for {dag_id}: {e}")
            return []
    
    def calculate_dag_metrics(self, dag_id: str, execution_date: str) -> DAGMetrics:
        """Calculate comprehensive metrics for a DAG run"""
        try:
            # Get DAG run info
            dag_runs = self.get_dag_runs(dag_id, limit=1)
            dag_run = next((run for run in dag_runs if run['execution_date'] == execution_date), None)
            
            if not dag_run:
                raise ValueError(f"DAG run not found: {dag_id}.{execution_date}")
            
            # Get task instances
            task_instances = self.get_task_instances(dag_id, execution_date)
            
            # Calculate metrics
            start_time = datetime.fromisoformat(dag_run['start_date'].replace('Z', '+00:00')) if dag_run.get('start_date') else None
            end_time = datetime.fromisoformat(dag_run['end_date'].replace('Z', '+00:00')) if dag_run.get('end_date') else None
            duration = None
            if start_time and end_time:
                duration = (end_time - start_time).total_seconds()
            elif start_time:
                duration = (datetime.now(start_time.tzinfo) - start_time).total_seconds()
            
            # Count task states
            task_states = {'success': 0, 'failed': 0, 'running': 0, 'queued': 0, 'upstream_failed': 0, 'skipped': 0}
            for task in task_instances:
                state = task.get('state', 'unknown')
                if state in task_states:
                    task_states[state] += 1
            
            total_tasks = len(task_instances)
            completed_tasks = task_states['success'] + task_states['failed']
            failed_tasks = task_states['failed'] + task_states['upstream_failed']
            running_tasks = task_states['running']
            queued_tasks = task_states['queued']
            
            # Check SLA
            sla_met = True
            if duration and duration > (self.config.max_duration_hours * 3600):
                sla_met = False
            
            metrics = DAGMetrics(
                dag_id=dag_id,
                execution_date=execution_date,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                state=dag_run.get('state', 'unknown'),
                task_count=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                running_tasks=running_tasks,
                queued_tasks=queued_tasks,
                sla_met=sla_met,
                sla_duration=self.config.max_duration_hours * 3600,
                last_updated=datetime.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating metrics for {dag_id}.{execution_date}: {e}")
            raise
    
    def check_sla_violations(self, metrics: DAGMetrics) -> List[SLAViolation]:
        """Check for SLA violations in DAG metrics"""
        violations = []
        
        # Check duration SLA
        if metrics.duration and metrics.duration > (self.config.max_duration_hours * 3600):
            severity = 'critical' if metrics.duration > (self.config.critical_threshold_hours * 3600) else 'warning'
            
            violation = SLAViolation(
                dag_id=metrics.dag_id,
                task_id=None,
                execution_date=metrics.execution_date,
                violation_type='duration',
                actual_duration=metrics.duration,
                sla_duration=self.config.max_duration_hours * 3600,
                severity=severity,
                timestamp=datetime.now(),
                message=f"DAG {metrics.dag_id} exceeded SLA duration: {metrics.duration/3600:.2f}h > {self.config.max_duration_hours}h",
                metadata={
                    'state': metrics.state,
                    'completed_tasks': metrics.completed_tasks,
                    'failed_tasks': metrics.failed_tasks,
                    'running_tasks': metrics.running_tasks
                }
            )
            violations.append(violation)
        
        # Check warning threshold
        elif metrics.duration and metrics.duration > (self.config.warning_threshold_hours * 3600):
            violation = SLAViolation(
                dag_id=metrics.dag_id,
                task_id=None,
                execution_date=metrics.execution_date,
                violation_type='duration',
                actual_duration=metrics.duration,
                sla_duration=self.config.max_duration_hours * 3600,
                severity='warning',
                timestamp=datetime.now(),
                message=f"DAG {metrics.dag_id} approaching SLA duration: {metrics.duration/3600:.2f}h > {self.config.warning_threshold_hours}h",
                metadata={
                    'state': metrics.state,
                    'completed_tasks': metrics.completed_tasks,
                    'running_tasks': metrics.running_tasks
                }
            )
            violations.append(violation)
        
        # Check failure rate
        if metrics.task_count > 0:
            failure_rate = metrics.failed_tasks / metrics.task_count
            if failure_rate > 0.1:  # 10% failure rate threshold
                violation = SLAViolation(
                    dag_id=metrics.dag_id,
                    task_id=None,
                    execution_date=metrics.execution_date,
                    violation_type='failure_rate',
                    actual_duration=None,
                    sla_duration=0,
                    severity='critical' if failure_rate > 0.5 else 'warning',
                    timestamp=datetime.now(),
                    message=f"DAG {metrics.dag_id} has high failure rate: {failure_rate:.1%} ({metrics.failed_tasks}/{metrics.task_count} tasks)",
                    metadata={
                        'failure_rate': failure_rate,
                        'failed_tasks': metrics.failed_tasks,
                        'total_tasks': metrics.task_count
                    }
                )
                violations.append(violation)
        
        # Check for long-running tasks
        if metrics.running_tasks > 0 and metrics.duration:
            avg_task_duration = metrics.duration / max(metrics.completed_tasks, 1)
            if avg_task_duration > (self.config.max_duration_hours * 3600 / metrics.task_count):
                violation = SLAViolation(
                    dag_id=metrics.dag_id,
                    task_id=None,
                    execution_date=metrics.execution_date,
                    violation_type='runtime',
                    actual_duration=metrics.duration,
                    sla_duration=self.config.max_duration_hours * 3600,
                    severity='warning',
                    timestamp=datetime.now(),
                    message=f"DAG {metrics.dag_id} has {metrics.running_tasks} tasks running for {metrics.duration/3600:.2f}h",
                    metadata={
                        'running_tasks': metrics.running_tasks,
                        'avg_task_duration': avg_task_duration
                    }
                )
                violations.append(violation)
        
        return violations
    
    def send_slack_alert(self, violation: SLAViolation):
        """Send SLA violation alert to Slack"""
        if not self.slack_client:
            logger.warning("Slack client not configured")
            return
        
        try:
            color = {
                'critical': 'danger',
                'warning': 'warning',
                'info': 'good'
            }.get(violation.severity, 'warning')
            
            attachment = {
                "color": color,
                "title": f"SLA Violation: {violation.violation_type.upper()}",
                "fields": [
                    {
                        "title": "DAG",
                        "value": violation.dag_id,
                        "short": True
                    },
                    {
                        "title": "Task",
                        "value": violation.task_id or "N/A",
                        "short": True
                    },
                    {
                        "title": "Execution Date",
                        "value": violation.execution_date,
                        "short": True
                    },
                    {
                        "title": "Severity",
                        "value": violation.severity.upper(),
                        "short": True
                    }
                ],
                "text": violation.message,
                "footer": "Airflow SLA Monitor",
                "ts": int(violation.timestamp.timestamp())
            }
            
            if violation.actual_duration:
                attachment["fields"].append({
                    "title": "Duration",
                    "value": f"{violation.actual_duration/3600:.2f}h",
                    "short": True
                })
            
            self.slack_client.send(text="SLA Alert", attachments=[attachment])
            logger.info(f"Slack alert sent for {violation.dag_id}")
            
        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
    
    def send_email_alert(self, violation: SLAViolation):
        """Send SLA violation alert via email"""
        if not all([self.config.email_smtp_server, self.config.email_username, self.config.email_recipients]):
            logger.warning("Email configuration incomplete")
            return
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.email_username
            msg['To'] = ', '.join(self.config.email_recipients)
            msg['Subject'] = f"Airflow SLA Violation: {violation.dag_id}"
            
            # Create body
            body = f"""
            SLA Violation Detected
            
            DAG: {violation.dag_id}
            Task: {violation.task_id or 'N/A'}
            Execution Date: {violation.execution_date}
            Violation Type: {violation.violation_type}
            Severity: {violation.severity.upper()}
            Timestamp: {violation.timestamp}
            
            Message: {violation.message}
            
            Additional Details:
            {json.dumps(violation.metadata, indent=2)}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port)
            server.starttls()
            server.login(self.config.email_username, self.config.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email alert sent for {violation.dag_id}")
            
        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
    
    def handle_violation(self, violation: SLAViolation):
        """Handle SLA violation (send alerts, callbacks, etc.)"""
        logger.warning(f"SLA Violation: {violation.message}")
        
        # Store violation
        self.violations.append(violation)
        
        # Send alerts
        if self.config.slack_webhook_url:
            self.send_slack_alert(violation)
        
        if self.config.email_recipients:
            self.send_email_alert(violation)
        
        # Call custom callbacks
        for callback in self.alert_callbacks:
            try:
                callback(violation)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def monitor_dag(self, dag_id: str, execution_date: str = None):
        """Monitor a specific DAG for SLA violations"""
        try:
            # Get latest execution date if not provided
            if not execution_date:
                dag_runs = self.get_dag_runs(dag_id, limit=1)
                if not dag_runs:
                    logger.info(f"No DAG runs found for {dag_id}")
                    return
                execution_date = dag_runs[0]['execution_date']
            
            # Calculate metrics
            metrics = self.calculate_dag_metrics(dag_id, execution_date)
            self.dag_metrics[f"{dag_id}.{execution_date}"] = metrics
            
            # Check for violations
            violations = self.check_sla_violations(metrics)
            
            # Handle violations
            for violation in violations:
                self.handle_violation(violation)
            
            logger.info(f"Monitored {dag_id}.{execution_date}: {len(violations)} violations")
            
        except Exception as e:
            logger.error(f"Error monitoring DAG {dag_id}: {e}")
    
    def monitor_all_dags(self, dag_ids: List[str]):
        """Monitor multiple DAGs"""
        for dag_id in dag_ids:
            try:
                self.monitor_dag(dag_id)
            except Exception as e:
                logger.error(f"Error monitoring {dag_id}: {e}")
    
    def start_continuous_monitoring(self, dag_ids: List[str]):
        """Start continuous monitoring in background"""
        async def monitoring_loop():
            while True:
                try:
                    self.monitor_all_dags(dag_ids)
                    await asyncio.sleep(self.config.check_interval_minutes * 60)
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute on error
        
        # Run in background thread
        def run_monitoring():
            asyncio.run(monitoring_loop())
        
        import threading
        monitoring_thread = threading.Thread(target=run_monitoring, daemon=True)
        monitoring_thread.start()
        
        logger.info(f"Started continuous monitoring for {len(dag_ids)} DAGs")
    
    def get_sla_report(self, days: int = 7) -> Dict[str, Any]:
        """Generate SLA compliance report"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Filter violations
        recent_violations = [
            v for v in self.violations 
            if v.timestamp >= cutoff_date
        ]
        
        # Calculate statistics
        total_violations = len(recent_violations)
        violations_by_type = {}
        violations_by_severity = {}
        violations_by_dag = {}
        
        for violation in recent_violations:
            # By type
            if violation.violation_type not in violations_by_type:
                violations_by_type[violation.violation_type] = 0
            violations_by_type[violation.violation_type] += 1
            
            # By severity
            if violation.severity not in violations_by_severity:
                violations_by_severity[violation.severity] = 0
            violations_by_severity[violation.severity] += 1
            
            # By DAG
            if violation.dag_id not in violations_by_dag:
                violations_by_dag[violation.dag_id] = 0
            violations_by_dag[violation.dag_id] += 1
        
        # Calculate SLA compliance rate
        total_dag_runs = len(self.dag_metrics)
        compliant_runs = len([m for m in self.dag_metrics.values() if m.sla_met])
        compliance_rate = compliant_runs / max(total_dag_runs, 1)
        
        report = {
            'period_days': days,
            'total_violations': total_violations,
            'violations_by_type': violations_by_type,
            'violations_by_severity': violations_by_severity,
            'violations_by_dag': violations_by_dag,
            'total_dag_runs': total_dag_runs,
            'compliant_runs': compliant_runs,
            'compliance_rate': compliance_rate,
            'generated_at': datetime.now().isoformat()
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None):
        """Save SLA report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sla_report_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"SLA report saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")


# Airflow DAG SLA callback function
def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """
    Airflow SLA miss callback function
    This function is called when an SLA is missed
    """
    from airflow.models import TaskInstance
    
    logger.error(f"SLA missed for DAG {dag.dag_id}")
    
    # Create violation
    violation = SLAViolation(
        dag_id=dag.dag_id,
        task_id=None,
        execution_date=str(blocking_tis[0].execution_date) if blocking_tis else 'unknown',
        violation_type='duration',
        actual_duration=None,
        sla_duration=dag.sla.total_seconds(),
        severity='critical',
        timestamp=datetime.now(),
        message=f"SLA missed for DAG {dag.dag_id}. Blocking tasks: {[ti.task_id for ti in blocking_tis]}",
        metadata={
            'blocking_tasks': [ti.task_id for ti in blocking_tis],
            'dag_sla_hours': dag.sla.total_seconds() / 3600
        }
    )
    
    # Send alert (this would be configured in the DAG)
    try:
        # This would use the SLA monitor instance
        logger.error(f"SLA Alert: {violation.message}")
    except Exception as e:
        logger.error(f"Error sending SLA alert: {e}")


# Example usage
if __name__ == "__main__":
    # Example SLA configuration
    sla_config = SLAConfig(
        max_duration_hours=1.0,
        warning_threshold_hours=0.75,
        critical_threshold_hours=1.5,
        slack_webhook_url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
        email_recipients=["oncall@finco.com", "devops@finco.com"]
    )
    
    # Create monitor
    monitor = SLAMonitor(sla_config)
    
    # Monitor specific DAG
    monitor.monitor_dag("daily_reconciliation_v2")
    
    # Generate report
    report = monitor.get_sla_report(days=7)
    print(f"SLA Report: {report}")
    
    # Save report
    monitor.save_report(report)
