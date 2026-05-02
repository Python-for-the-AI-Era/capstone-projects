"""
Airflow DAG Forensic Audit and Diagnosis Module
Comprehensive debugging tools for stuck Airflow DAGs at Finco Bank
"""

import asyncio
import logging
import psycopg2
import requests
import json
import time
import subprocess
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

logger = logging.getLogger(__name__)


@dataclass
class TaskInstanceInfo:
    """Information about a running task instance"""
    dag_id: str
    task_id: str
    execution_date: str
    state: str
    start_date: Optional[str]
    end_date: Optional[str]
    duration: Optional[float]
    pid: Optional[int]
    hostname: str
    queue: str
    max_tries: int
    try_number: int
    
    def is_stuck(self, max_duration_hours: float = 2.0) -> bool:
        """Check if task is stuck (running for too long)"""
        if self.state != 'running' or not self.start_date:
            return False
        
        start_time = datetime.fromisoformat(self.start_date.replace('Z', '+00:00'))
        duration = datetime.now(start_time.tzinfo) - start_time
        return duration.total_seconds() > (max_duration_hours * 3600)


@dataclass
class WorkerInfo:
    """Information about Airflow worker"""
    hostname: str
    pid: int
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    running_tasks: int
    last_heartbeat: Optional[str]
    is_alive: bool


@dataclass
class DatabaseLockInfo:
    """Information about database locks"""
    pid: int
    database: str
    relation: str
    mode: str
    granted: bool
    query: Optional[str]
    wait_time: float
    blocked_by: Optional[int]


class AirflowForensics:
    """
    Comprehensive forensic analysis tool for Airflow DAG issues
    """
    
    def __init__(self, airflow_db_uri: str, airflow_api_base: str = "http://localhost:8080/api/v1"):
        self.airflow_db_uri = airflow_db_uri
        self.airflow_api_base = airflow_api_base
        self.connection = None
        
        logger.info("AirflowForensics initialized")
    
    def connect_to_database(self) -> bool:
        """Connect to Airflow PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(self.airflow_db_uri)
            self.connection.autocommit = False
            logger.info("Connected to Airflow database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    def get_stuck_task_instances(self, max_duration_hours: float = 2.0) -> List[TaskInstanceInfo]:
        """
        Get all task instances that have been running too long
        
        Args:
            max_duration_hours: Maximum allowed duration in hours
            
        Returns:
            List of stuck task instances
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        query = """
        SELECT 
            ti.dag_id,
            ti.task_id,
            ti.execution_date,
            ti.state,
            ti.start_date,
            ti.end_date,
            EXTRACT(EPOCH FROM (COALESCE(ti.end_date, NOW()) - ti.start_date)) as duration,
            ti.pid,
            ti.hostname,
            ti.queue,
            ti.max_tries,
            ti.try_number
        FROM task_instance ti
        WHERE ti.state = 'running'
        AND ti.start_date < NOW() - INTERVAL '%s hours'
        ORDER BY ti.start_date
        """
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (max_duration_hours,))
                results = cursor.fetchall()
                
                stuck_tasks = []
                for row in results:
                    task_info = TaskInstanceInfo(
                        dag_id=row[0],
                        task_id=row[1],
                        execution_date=str(row[2]),
                        state=row[3],
                        start_date=str(row[4]) if row[4] else None,
                        end_date=str(row[5]) if row[5] else None,
                        duration=float(row[6]) if row[6] else None,
                        pid=row[7],
                        hostname=row[8],
                        queue=row[9],
                        max_tries=row[10],
                        try_number=row[11]
                    )
                    stuck_tasks.append(task_info)
                
                logger.info(f"Found {len(stuck_tasks)} stuck tasks")
                return stuck_tasks
                
        except Exception as e:
            logger.error(f"Error querying stuck tasks: {e}")
            raise
    
    def get_database_locks(self) -> List[DatabaseLockInfo]:
        """
        Get current database locks that might be blocking tasks
        
        Returns:
            List of database lock information
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        query = """
        SELECT 
            bl.pid,
            bl.database,
            bl.relation,
            bl.mode,
            bl.granted,
            a.query,
            EXTRACT(EPOCH FROM (NOW() - a.query_start)) as wait_time,
            bl.blocked_by
        FROM pg_locks bl
        LEFT JOIN pg_stat_activity a ON bl.pid = a.pid
        WHERE bl.granted = false
        OR (bl.granted = true AND EXISTS (
            SELECT 1 FROM pg_locks bl2 
            WHERE bl2.pid = bl.blocked_by 
            AND bl2.granted = false
        ))
        ORDER BY bl.pid
        """
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                locks = []
                for row in results:
                    lock_info = DatabaseLockInfo(
                        pid=row[0],
                        database=row[1],
                        relation=row[2],
                        mode=row[3],
                        granted=row[4],
                        query=row[5],
                        wait_time=float(row[6]) if row[6] else 0.0,
                        blocked_by=row[7]
                    )
                    locks.append(lock_info)
                
                logger.info(f"Found {len(locks)} database locks")
                return locks
                
        except Exception as e:
            logger.error(f"Error querying database locks: {e}")
            raise
    
    def get_worker_status(self) -> List[WorkerInfo]:
        """
        Get status of Airflow workers
        
        Returns:
            List of worker information
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        query = """
        SELECT 
            w.hostname,
            w.pid,
            w.last_heartbeat,
            COUNT(ti.task_id) as running_tasks
        FROM worker w
        LEFT JOIN task_instance ti ON w.hostname = ti.hostname 
        AND ti.state = 'running'
        GROUP BY w.hostname, w.pid, w.last_heartbeat
        """
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                workers = []
                for row in results:
                    hostname, pid, last_heartbeat, running_tasks = row
                    
                    # Get system metrics for this worker
                    try:
                        process = psutil.Process(pid)
                        cpu_percent = process.cpu_percent()
                        memory_info = process.memory_info()
                        memory_mb = memory_info.rss / 1024 / 1024
                        memory_percent = process.memory_percent()
                        is_alive = process.is_running()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        cpu_percent = 0.0
                        memory_mb = 0.0
                        memory_percent = 0.0
                        is_alive = False
                    
                    worker_info = WorkerInfo(
                        hostname=hostname,
                        pid=pid,
                        cpu_percent=cpu_percent,
                        memory_percent=memory_percent,
                        memory_mb=memory_mb,
                        running_tasks=running_tasks,
                        last_heartbeat=str(last_heartbeat) if last_heartbeat else None,
                        is_alive=is_alive
                    )
                    workers.append(worker_info)
                
                logger.info(f"Found {len(workers)} workers")
                return workers
                
        except Exception as e:
            logger.error(f"Error querying worker status: {e}")
            raise
    
    def get_task_logs(self, dag_id: str, task_id: str, execution_date: str) -> str:
        """
        Get logs for a specific task instance
        
        Args:
            dag_id: DAG ID
            task_id: Task ID
            execution_date: Execution date
            
        Returns:
            Log content
        """
        try:
            # Try to get logs from Airflow API first
            url = f"{self.airflow_api_base}/dags/{dag_id}/dagRuns/{execution_date}/taskInstances/{task_id}/logs"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
            
            # Fallback to local log files
            log_path = f"/opt/airflow/logs/{dag_id}/{task_id}/{execution_date}.log"
            
            if Path(log_path).exists():
                with open(log_path, 'r') as f:
                    return f.read()
            
            return f"No logs found for {dag_id}.{task_id}.{execution_date}"
            
        except Exception as e:
            logger.error(f"Error getting task logs: {e}")
            return f"Error retrieving logs: {e}"
    
    def analyze_task_process(self, pid: int) -> Dict[str, Any]:
        """
        Analyze a running task process for hangs
        
        Args:
            pid: Process ID
            
        Returns:
            Process analysis results
        """
        try:
            process = psutil.Process(pid)
            
            # Get basic process info
            analysis = {
                'pid': pid,
                'status': process.status(),
                'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                'cpu_percent': process.cpu_percent(),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'num_threads': process.num_threads(),
                'connections': len(process.connections()),
                'open_files': len(process.open_files()),
                'command_line': ' '.join(process.cmdline()),
                'cwd': process.cwd(),
                'parent_pid': process.ppid()
            }
            
            # Check for network connections (potential hanging HTTP calls)
            connections = []
            for conn in process.connections():
                if conn.status == 'ESTABLISHED':
                    connections.append({
                        'local_address': f"{conn.laddr.ip}:{conn.laddr.port}",
                        'remote_address': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                        'status': conn.status
                    })
            analysis['network_connections'] = connections
            
            # Check for open file handles
            open_files = []
            try:
                for file in process.open_files():
                    open_files.append({
                        'path': file.path,
                        'fd': file.fd
                    })
                analysis['open_file_details'] = open_files[:10]  # Limit to 10 files
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                analysis['open_file_details'] = []
            
            # Get thread stack traces if possible
            threads = []
            try:
                for thread in process.threads():
                    threads.append({
                        'id': thread.id,
                        'user_time': thread.user_time,
                        'system_time': thread.system_time
                    })
                analysis['threads'] = threads
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                analysis['threads'] = []
            
            return analysis
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return {
                'pid': pid,
                'error': f"Cannot access process: {e}",
                'status': 'unknown'
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """
        Check system-wide resource usage
        
        Returns:
            System resource information
        """
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            network = psutil.net_io_counters()
            
            # Load average
            load_avg = psutil.getloadavg()
            
            return {
                'cpu_percent': cpu_percent,
                'memory_total_gb': memory.total / 1024 / 1024 / 1024,
                'memory_available_gb': memory.available / 1024 / 1024 / 1024,
                'memory_percent': memory.percent,
                'disk_total_gb': disk.total / 1024 / 1024 / 1024,
                'disk_free_gb': disk.free / 1024 / 1024 / 1024,
                'disk_percent': (disk.used / disk.total) * 100,
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'load_average_1min': load_avg[0],
                'load_average_5min': load_avg[1],
                'load_average_15min': load_avg[2],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return {'error': str(e)}
    
    def generate_forensic_report(self, dag_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive forensic report
        
        Args:
            dag_id: Optional DAG ID to focus on
            
        Returns:
            Forensic report
        """
        logger.info("Generating forensic report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'dag_id': dag_id,
            'system_resources': self.check_system_resources(),
            'stuck_tasks': [],
            'database_locks': [],
            'worker_status': [],
            'analysis': []
        }
        
        try:
            # Get stuck tasks
            stuck_tasks = self.get_stuck_task_instances()
            if dag_id:
                stuck_tasks = [t for t in stuck_tasks if t.dag_id == dag_id]
            report['stuck_tasks'] = [asdict(task) for task in stuck_tasks]
            
            # Analyze each stuck task
            for task in stuck_tasks:
                if task.pid:
                    process_analysis = self.analyze_task_process(task.pid)
                    report['analysis'].append({
                        'task': asdict(task),
                        'process_analysis': process_analysis,
                        'logs': self.get_task_logs(task.dag_id, task.task_id, task.execution_date)[-1000:]  # Last 1000 chars
                    })
            
            # Get database locks
            report['database_locks'] = [asdict(lock) for lock in self.get_database_locks()]
            
            # Get worker status
            report['worker_status'] = [asdict(worker) for worker in self.get_worker_status()]
            
            # Generate recommendations
            report['recommendations'] = self._generate_recommendations(report)
            
        except Exception as e:
            logger.error(f"Error generating forensic report: {e}")
            report['error'] = str(e)
        
        return report
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Check for stuck tasks
        if report['stuck_tasks']:
            recommendations.append(
                f"Found {len(report['stuck_tasks'])} stuck tasks. "
                "Consider killing long-running processes and investigating root cause."
            )
        
        # Check database locks
        blocking_locks = [lock for lock in report['database_locks'] if not lock['granted']]
        if blocking_locks:
            recommendations.append(
                f"Found {len(blocking_locks)} blocking database locks. "
                "Check for long-running transactions or deadlocks."
            )
        
        # Check system resources
        system = report.get('system_resources', {})
        if system.get('memory_percent', 0) > 90:
            recommendations.append(
                "High memory usage detected. Consider increasing memory or optimizing queries."
            )
        
        if system.get('cpu_percent', 0) > 90:
            recommendations.append(
                "High CPU usage detected. Check for infinite loops or CPU-intensive operations."
            )
        
        if system.get('disk_percent', 0) > 90:
            recommendations.append(
                "High disk usage detected. Check for log file growth or data accumulation."
            )
        
        # Check worker health
        unhealthy_workers = [w for w in report['worker_status'] if not w['is_alive']]
        if unhealthy_workers:
            recommendations.append(
                f"Found {len(unhealthy_workers)} unhealthy workers. "
                "Restart Airflow workers and check resource allocation."
            )
        
        # Check for hanging network connections
        hanging_tasks = []
        for analysis in report['analysis']:
            process = analysis.get('process_analysis', {})
            if process.get('network_connections'):
                hanging_tasks.append(analysis['task']['task_id'])
        
        if hanging_tasks:
            recommendations.append(
                f"Tasks {hanging_tasks} have active network connections. "
                "Check for hanging HTTP calls without timeouts."
            )
        
        if not recommendations:
            recommendations.append("No obvious issues detected. Monitor system closely.")
        
        return recommendations
    
    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None):
        """Save forensic report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"airflow_forensic_report_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Forensic report saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")
    
    def cleanup(self):
        """Clean up database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")


# CLI interface for quick diagnosis
def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Airflow DAG Forensic Analysis")
    parser.add_argument("--db-uri", required=True, help="Airflow database URI")
    parser.add_argument("--dag-id", help="Specific DAG to analyze")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--max-duration", type=float, default=2.0, 
                       help="Maximum duration in hours to consider stuck")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run forensic analysis
    forensics = AirflowForensics(args.db_uri)
    
    try:
        if not forensics.connect_to_database():
            print("Failed to connect to database")
            sys.exit(1)
        
        print("🔍 Starting Airflow forensic analysis...")
        
        # Generate report
        report = forensics.generate_forensic_report(args.dag_id)
        
        # Print summary
        print(f"\n📊 Forensic Report Summary:")
        print(f"   Stuck Tasks: {len(report['stuck_tasks'])}")
        print(f"   Database Locks: {len(report['database_locks'])}")
        print(f"   Workers: {len(report['worker_status'])}")
        
        if report['stuck_tasks']:
            print(f"\n🚨 Stuck Tasks:")
            for task in report['stuck_tasks']:
                duration = task['duration'] or 0
                print(f"   - {task['dag_id']}.{task['task_id']} (running for {duration:.1f}s)")
        
        if report['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in report['recommendations']:
                print(f"   - {rec}")
        
        # Save report
        forensics.save_report(report, args.output)
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)
    finally:
        forensics.cleanup()


if __name__ == "__main__":
    main()
