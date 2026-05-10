#!/usr/bin/env python3
"""
Debug script for stuck Airflow DAG - Finco Bank reconciliation.

This script helps diagnose why the DAG is stuck by checking:
1. Airflow worker logs for stuck tasks
2. Database locks and long-running queries
3. HTTP call timeouts
4. Disk space issues
5. System resource usage
"""

import argparse
import logging
import subprocess
import time
import json
import psycopg2
import requests
from datetime import datetime, timedelta
from pathlib import Path
import psutil
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AirflowDAGDebugger:
    """Debug tool for stuck Airflow DAGs."""
    
    def __init__(self, dag_id: str, airflow_home: str = "/opt/airflow"):
        """
        Initialize debugger.
        
        Args:
            dag_id: ID of the stuck DAG
            airflow_home: Airflow home directory
        """
        self.dag_id = dag_id
        self.airflow_home = airflow_home
        self.debug_results = {}
        
        logger.info(f"Initializing debugger for DAG: {dag_id}")
    
    def check_worker_logs(self) -> dict:
        """
        Check Airflow worker logs for stuck tasks.
        
        Returns:
            Dictionary with log analysis results
        """
        logger.info("Checking Airflow worker logs...")
        
        results = {
            'stuck_tasks': [],
            'error_patterns': [],
            'timeout_indicators': [],
            'db_lock_indicators': []
        }
        
        try:
            # Get running task instances
            cmd = [
                'airflow', 'tasks', 'list', '-d', self.dag_id
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse task list
                tasks = result.stdout.strip().split('\n')
                for task in tasks:
                    if task.strip():
                        task_info = self._get_task_instance_info(task.strip())
                        if task_info.get('state') == 'running':
                            duration = self._get_task_duration(task_info)
                            if duration > timedelta(hours=1):  # Running for over 1 hour
                                results['stuck_tasks'].append({
                                    'task_id': task.strip(),
                                    'duration': str(duration),
                                    'start_date': task_info.get('start_date'),
                                    'execution_date': task_info.get('execution_date')
                                })
            
            # Check worker logs for error patterns
            log_patterns = self._analyze_worker_logs()
            results.update(log_patterns)
            
        except Exception as e:
            logger.error(f"Error checking worker logs: {e}")
            results['error'] = str(e)
        
        self.debug_results['worker_logs'] = results
        return results
    
    def check_database_locks(self) -> dict:
        """
        Check for database locks and long-running queries.
        
        Returns:
            Dictionary with database analysis results
        """
        logger.info("Checking database locks...")
        
        results = {
            'active_locks': [],
            'long_running_queries': [],
            'blocking_sessions': [],
            'connection_count': 0
        }
        
        try:
            # Connect to Airflow database
            conn = psycopg2.connect(
                host=self._get_db_host(),
                database=self._get_db_name(),
                user=self._get_db_user(),
                password=self._get_db_password()
            )
            
            cursor = conn.cursor()
            
            # Check for active locks
            cursor.execute("""
            SELECT 
                pid,
                state,
                query_start,
                now() - query_start AS duration,
                query
            FROM pg_stat_activity 
            WHERE state = 'active' 
            AND now() - query_start > interval '5 minutes'
            ORDER BY duration DESC
            """)
            
            for row in cursor.fetchall():
                results['active_locks'].append({
                    'pid': row[0],
                    'state': row[1],
                    'query_start': row[2],
                    'duration': str(row[3]),
                    'query': row[4][:200] + '...' if row[4] and len(row[4]) > 200 else row[4]
                })
            
            # Check for blocking sessions
            cursor.execute("""
            SELECT 
                blocked_locks.pid AS blocked_pid,
                blocked_activity.usename AS blocked_user,
                blocking_locks.pid AS blocking_pid,
                blocking_activity.usename AS blocking_user,
                blocked_activity.query AS blocked_statement,
                blocking_activity.query AS current_statement_in_blocking_process
            FROM pg_catalog.pg_locks blocked_locks
            JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
            JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
            JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
            WHERE NOT blocked_locks.granted
            """)
            
            for row in cursor.fetchall():
                results['blocking_sessions'].append({
                    'blocked_pid': row[0],
                    'blocked_user': row[1],
                    'blocking_pid': row[2],
                    'blocking_user': row[3],
                    'blocked_statement': row[4],
                    'blocking_statement': row[5]
                })
            
            # Get connection count
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            results['connection_count'] = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error checking database locks: {e}")
            results['error'] = str(e)
        
        self.debug_results['database_locks'] = results
        return results
    
    def check_http_timeouts(self) -> dict:
        """
        Check for HTTP calls without timeouts in the DAG code.
        
        Returns:
            Dictionary with HTTP timeout analysis
        """
        logger.info("Checking for HTTP timeout issues...")
        
        results = {
            'http_calls_without_timeout': [],
            'potential_timeout_issues': [],
            'external_api_status': {}
        }
        
        try:
            # Read the DAG file
            dag_file = Path(self.airflow_home) / 'dags' / f'{self.dag_id}.py'
            
            if dag_file.exists():
                with open(dag_file, 'r') as f:
                    content = f.read()
                
                # Find HTTP calls without timeout
                http_patterns = [
                    r'requests\.(get|post|put|delete|patch)\([^)]*\)(?!.*timeout)',
                    r'HttpOperator\([^)]*\)(?!.*http_conn_id)',
                ]
                
                for pattern in http_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        results['http_calls_without_timeout'].append({
                            'line': line_num,
                            'match': match.group(),
                            'context': self._get_line_context(content, line_num)
                        })
                
                # Check for external API URLs
                api_urls = re.findall(r'(https?://[^\s\'"]+)', content)
                for url in set(api_urls):
                    try:
                        # Test API connectivity with timeout
                        response = requests.get(url, timeout=10)
                        results['external_api_status'][url] = {
                            'status_code': response.status_code,
                            'response_time': response.elapsed.total_seconds(),
                            'accessible': True
                        }
                    except requests.exceptions.Timeout:
                        results['external_api_status'][url] = {
                            'error': 'Timeout',
                            'accessible': False
                        }
                        results['potential_timeout_issues'].append(url)
                    except Exception as e:
                        results['external_api_status'][url] = {
                            'error': str(e),
                            'accessible': False
                        }
            
        except Exception as e:
            logger.error(f"Error checking HTTP timeouts: {e}")
            results['error'] = str(e)
        
        self.debug_results['http_timeouts'] = results
        return results
    
    def check_system_resources(self) -> dict:
        """
        Check system resources that might cause DAG to hang.
        
        Returns:
            Dictionary with system resource analysis
        """
        logger.info("Checking system resources...")
        
        results = {
            'cpu_usage': psutil.cpu_percent(interval=1),
            'memory_usage': psutil.virtual_memory()._asdict(),
            'disk_usage': {},
            'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
            'process_count': len(psutil.pids()),
            'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
        
        # Check disk usage for critical paths
        critical_paths = [
            self.airflow_home,
            '/tmp',
            '/var/log',
            '/'
        ]
        
        for path in critical_paths:
            try:
                disk_usage = psutil.disk_usage(path)
                results['disk_usage'][path] = {
                    'total': disk_usage.total,
                    'used': disk_usage.used,
                    'free': disk_usage.free,
                    'percent': (disk_usage.used / disk_usage.total) * 100
                }
            except Exception as e:
                results['disk_usage'][path] = {'error': str(e)}
        
        # Check for Airflow-specific resource usage
        try:
            airflow_processes = []
            for pid in psutil.pids():
                try:
                    proc = psutil.Process(pid)
                    if 'airflow' in proc.name().lower():
                        airflow_processes.append({
                            'pid': pid,
                            'name': proc.name(),
                            'cpu_percent': proc.cpu_percent(),
                            'memory_percent': proc.memory_percent(),
                            'status': proc.status(),
                            'create_time': proc.create_time()
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            results['airflow_processes'] = airflow_processes
            
        except Exception as e:
            results['airflow_processes_error'] = str(e)
        
        self.debug_results['system_resources'] = results
        return results
    
    def check_airflow_metadata(self) -> dict:
        """
        Check Airflow metadata for stuck DAG runs.
        
        Returns:
            Dictionary with metadata analysis
        """
        logger.info("Checking Airflow metadata...")
        
        results = {
            'dag_runs': [],
            'task_instances': [],
            'dag_status': 'unknown'
        }
        
        try:
            # Connect to Airflow metadata database
            conn = psycopg2.connect(
                host=self._get_db_host(),
                database=self._get_db_name(),
                user=self._get_db_user(),
                password=self._get_db_password()
            )
            
            cursor = conn.cursor()
            
            # Get DAG runs
            cursor.execute("""
            SELECT 
                dag_id,
                run_id,
                state,
                execution_date,
                start_date,
                end_date,
                now() - start_date AS duration
            FROM dag_run 
            WHERE dag_id = %s
            ORDER BY execution_date DESC
            LIMIT 10
            """, (self.dag_id,))
            
            for row in cursor.fetchall():
                results['dag_runs'].append({
                    'dag_id': row[0],
                    'run_id': row[1],
                    'state': row[2],
                    'execution_date': row[3],
                    'start_date': row[4],
                    'end_date': row[5],
                    'duration': str(row[6]) if row[6] else None
                })
            
            # Get task instances
            cursor.execute("""
            SELECT 
                task_id,
                state,
                start_date,
                end_date,
                now() - start_date AS duration,
                max_tries,
                try_number
            FROM task_instance 
            WHERE dag_id = %s
            AND execution_date = (
                SELECT execution_date 
                FROM dag_run 
                WHERE dag_id = %s 
                ORDER BY execution_date DESC 
                LIMIT 1
            )
            ORDER BY start_date DESC
            """, (self.dag_id, self.dag_id))
            
            for row in cursor.fetchall():
                results['task_instances'].append({
                    'task_id': row[0],
                    'state': row[1],
                    'start_date': row[2],
                    'end_date': row[3],
                    'duration': str(row[4]) if row[4] else None,
                    'max_tries': row[5],
                    'try_number': row[6]
                })
            
            cursor.close()
            conn.close()
            
            # Determine overall DAG status
            if results['dag_runs']:
                latest_run = results['dag_runs'][0]
                results['dag_status'] = latest_run['state']
            
        except Exception as e:
            logger.error(f"Error checking Airflow metadata: {e}")
            results['error'] = str(e)
        
        self.debug_results['airflow_metadata'] = results
        return results
    
    def generate_diagnosis_report(self) -> dict:
        """
        Generate comprehensive diagnosis report.
        
        Returns:
            Complete diagnosis report
        """
        logger.info("Generating comprehensive diagnosis report...")
        
        # Run all checks
        self.check_worker_logs()
        self.check_database_locks()
        self.check_http_timeouts()
        self.check_system_resources()
        self.check_airflow_metadata()
        
        # Analyze results and identify bottlenecks
        bottlenecks = []
        recommendations = []
        
        # Analyze worker logs
        worker_logs = self.debug_results.get('worker_logs', {})
        if worker_logs.get('stuck_tasks'):
            bottlenecks.append({
                'type': 'stuck_tasks',
                'severity': 'high',
                'description': f"{len(worker_logs['stuck_tasks'])} tasks are stuck running",
                'details': worker_logs['stuck_tasks']
            })
            recommendations.append("Kill stuck task instances and restart the DAG")
        
        # Analyze database locks
        db_locks = self.debug_results.get('database_locks', {})
        if db_locks.get('active_locks'):
            bottlenecks.append({
                'type': 'database_locks',
                'severity': 'high',
                'description': f"{len(db_locks['active_locks'])} long-running database queries",
                'details': db_locks['active_locks']
            })
            recommendations.append("Identify and terminate blocking database sessions")
        
        # Analyze HTTP timeouts
        http_timeouts = self.debug_results.get('http_timeouts', {})
        if http_timeouts.get('http_calls_without_timeout'):
            bottlenecks.append({
                'type': 'http_timeouts',
                'severity': 'high',
                'description': f"{len(http_timeouts['http_calls_without_timeout'])} HTTP calls without timeout",
                'details': http_timeouts['http_calls_without_timeout']
            })
            recommendations.append("Add timeout parameters to all HTTP calls")
        
        # Analyze system resources
        system_resources = self.debug_results.get('system_resources', {})
        disk_usage = system_resources.get('disk_usage', {})
        for path, usage in disk_usage.items():
            if isinstance(usage, dict) and usage.get('percent', 0) > 90:
                bottlenecks.append({
                    'type': 'disk_space',
                    'severity': 'high',
                    'description': f"Low disk space on {path}: {usage['percent']:.1f}%",
                    'details': usage
                })
                recommendations.append(f"Free up disk space on {path}")
        
        # Create final report
        report = {
            'dag_id': self.dag_id,
            'diagnosis_time': datetime.now().isoformat(),
            'bottlenecks': bottlenecks,
            'recommendations': recommendations,
            'debug_results': self.debug_results,
            'summary': {
                'total_bottlenecks': len(bottlenecks),
                'high_severity_issues': len([b for b in bottlenecks if b['severity'] == 'high']),
                'most_likely_cause': self._determine_most_likely_cause(bottlenecks)
            }
        }
        
        return report
    
    def save_report(self, report: dict, output_file: str = None):
        """
        Save diagnosis report to file.
        
        Args:
            report: Diagnosis report
            output_file: Output file path
        """
        if output_file is None:
            output_file = f"logs/diagnosis_{self.dag_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Diagnosis report saved to: {output_file}")
    
    # Helper methods
    def _get_task_instance_info(self, task_id: str) -> dict:
        """Get task instance information."""
        # This would typically query Airflow metadata
        return {'state': 'running', 'start_date': datetime.now()}
    
    def _get_task_duration(self, task_info: dict) -> timedelta:
        """Calculate task duration."""
        start_date = task_info.get('start_date')
        if start_date:
            return datetime.now() - start_date
        return timedelta(0)
    
    def _analyze_worker_logs(self) -> dict:
        """Analyze worker logs for error patterns."""
        patterns = {
            'error_patterns': [],
            'timeout_indicators': [],
            'db_lock_indicators': []
        }
        
        # This would typically read actual log files
        # For now, return empty patterns
        return patterns
    
    def _get_line_context(self, content: str, line_num: int, context_lines: int = 3) -> str:
        """Get context around a specific line."""
        lines = content.split('\n')
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        return '\n'.join(lines[start:end])
    
    def _get_db_host(self) -> str:
        """Get database host from environment or config."""
        import os
        return os.getenv('AIRFLOW_DB_HOST', 'localhost')
    
    def _get_db_name(self) -> str:
        """Get database name from environment or config."""
        import os
        return os.getenv('AIRFLOW_DB_NAME', 'airflow')
    
    def _get_db_user(self) -> str:
        """Get database user from environment or config."""
        import os
        return os.getenv('AIRFLOW_DB_USER', 'airflow')
    
    def _get_db_password(self) -> str:
        """Get database password from environment or config."""
        import os
        return os.getenv('AIRFLOW_DB_PASSWORD', 'airflow')
    
    def _determine_most_likely_cause(self, bottlenecks: list) -> str:
        """Determine the most likely cause of the stuck DAG."""
        if not bottlenecks:
            return "No clear bottlenecks identified"
        
        # Prioritize by severity and type
        high_severity_bottlenecks = [b for b in bottlenecks if b['severity'] == 'high']
        
        if high_severity_bottlenecks:
            # Check for HTTP timeouts first (most common cause)
            http_bottlenecks = [b for b in high_severity_bottlenecks if b['type'] == 'http_timeouts']
            if http_bottlenecks:
                return "HTTP calls without timeout parameters"
            
            # Check for database locks
            db_bottlenecks = [b for b in high_severity_bottlenecks if b['type'] == 'database_locks']
            if db_bottlenecks:
                return "Database locks and long-running queries"
            
            # Check for stuck tasks
            task_bottlenecks = [b for b in high_severity_bottlenecks if b['type'] == 'stuck_tasks']
            if task_bottlenecks:
                return "Stuck task instances"
        
        return "Multiple issues identified - detailed analysis required"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Debug stuck Airflow DAG')
    parser.add_argument('--dag-id', required=True, help='DAG ID to debug')
    parser.add_argument('--airflow-home', default='/opt/airflow', help='Airflow home directory')
    parser.add_argument('--output', help='Output file for diagnosis report')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create debugger
    debugger = AirflowDAGDebugger(args.dag_id, args.airflow_home)
    
    # Generate diagnosis report
    report = debugger.generate_diagnosis_report()
    
    # Print summary
    print("\n" + "="*60)
    print("AIRFLOW DAG DIAGNOSIS REPORT")
    print("="*60)
    print(f"DAG ID: {report['dag_id']}")
    print(f"Diagnosis Time: {report['diagnosis_time']}")
    print(f"Total Bottlenecks: {report['summary']['total_bottlenecks']}")
    print(f"High Severity Issues: {report['summary']['high_severity_issues']}")
    print(f"Most Likely Cause: {report['summary']['most_likely_cause']}")
    
    if report['bottlenecks']:
        print("\nBOTTLENECKS:")
        for i, bottleneck in enumerate(report['bottlenecks'], 1):
            print(f"{i}. {bottleneck['type'].upper()} ({bottleneck['severity']})")
            print(f"   {bottleneck['description']}")
    
    if report['recommendations']:
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
    
    print("="*60)
    
    # Save report
    debugger.save_report(report, args.output)
    
    return len(report['bottlenecks']) == 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
