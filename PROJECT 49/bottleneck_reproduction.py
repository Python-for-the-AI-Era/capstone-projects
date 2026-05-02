"""
Bottleneck Reproduction and Analysis Module
Reproduces and identifies hanging code paths in Airflow DAGs
"""

import asyncio
import logging
import time
import threading
import requests
import json
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import traceback
import psutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class HangingScenario:
    """Represents a scenario that can cause hanging"""
    name: str
    description: str
    code_function: Callable
    expected_hang_time: float
    timeout_to_kill: float
    symptoms: List[str]


@dataclass
class ReproductionResult:
    """Result of bottleneck reproduction attempt"""
    scenario_name: str
    hung: bool
    hang_duration: float
    timeout_triggered: bool
    error_message: Optional[str]
    stack_trace: Optional[str]
    system_impact: Dict[str, Any]
    timestamp: str


class HangingCodeReproducer:
    """
    Reproduces various hanging scenarios to identify bottlenecks
    """
    
    def __init__(self):
        self.scenarios = []
        self.results = []
        self.current_process = psutil.Process()
        
        logger.info("HangingCodeReproducer initialized")
    
    def register_scenario(self, scenario: HangingScenario):
        """Register a hanging scenario for testing"""
        self.scenarios.append(scenario)
        logger.info(f"Registered scenario: {scenario.name}")
    
    def simulate_hanging_http_call(self, timeout: Optional[float] = None):
        """
        Simulate hanging HTTP call without timeout
        This is the most common cause of stuck Airflow tasks
        """
        logger.info("Simulating hanging HTTP call...")
        
        # Create a server that never responds
        def start_hanging_server():
            import socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', 0))
            port = server_socket.getsockname()[1]
            server_socket.listen(1)
            
            def handle_client():
                try:
                    client, addr = server_socket.accept()
                    # Never respond - just keep connection open
                    time.sleep(3600)  # Sleep for 1 hour
                except:
                    pass
            
            # Start handler in thread
            threading.Thread(target=handle_client, daemon=True).start()
            return port
        
        # Start hanging server
        port = start_hanging_server()
        
        try:
            # Make request without timeout (this will hang)
            response = requests.post(
                f"http://localhost:{port}/reconcile",
                json={"records": [{"id": 1, "amount": 100}]},
                timeout=timeout  # None means no timeout
            )
            return response.json()
        except Exception as e:
            logger.error(f"HTTP call failed: {e}")
            raise
    
    def simulate_infinite_loop(self):
        """Simulate infinite loop"""
        logger.info("Simulating infinite loop...")
        
        counter = 0
        while True:
            counter += 1
            if counter % 1000000 == 0:
                # Occasionally check if we should continue
                time.sleep(0.001)  # Tiny sleep to prevent 100% CPU
    
    def simulate_database_lock_wait(self):
        """Simulate database lock wait"""
        logger.info("Simulating database lock wait...")
        
        import psycopg2
        from psycopg2 import sql, OperationalError
        
        # Simulate a long-running transaction that holds locks
        try:
            conn = psycopg2.connect(
                "postgresql://airflow:airflow@localhost/airflow",
                autocommit=False
            )
            
            cursor = conn.cursor()
            
            # Start transaction
            cursor.execute("BEGIN")
            
            # Lock some rows (simulate reconciliation lock)
            cursor.execute("""
                SELECT * FROM task_instance 
                WHERE state = 'running' 
                FOR UPDATE
            """)
            
            # Sleep forever while holding locks
            while True:
                time.sleep(1)
                
        except OperationalError as e:
            logger.error(f"Database error: {e}")
            raise
    
    def simulate_full_disk_write(self):
        """Simulate hanging due to full disk"""
        logger.info("Simulating full disk write...")
        
        # Try to write a very large file
        try:
            with open("/tmp/large_file.log", "w") as f:
                for i in range(1000000):  # Try to write ~1GB
                    f.write(f"Log entry {i}: This is a large log entry that might fill up disk space\n")
                    if i % 10000 == 0:
                        f.flush()  # Force write to disk
        except OSError as e:
            logger.error(f"Disk write error: {e}")
            raise
    
    def simulate_memory_leak(self):
        """Simulate memory leak that causes hanging"""
        logger.info("Simulating memory leak...")
        
        data = []
        try:
            while True:
                # Keep adding data to memory
                data.append("x" * 1024 * 1024)  # 1MB per iteration
                time.sleep(0.01)
        except MemoryError as e:
            logger.error(f"Memory error: {e}")
            raise
    
    def simulate_blocking_file_operation(self):
        """Simulate blocking file operation"""
        logger.info("Simulating blocking file operation...")
        
        # Try to read from a named pipe that never gets data
        try:
            import os
            
            # Create named pipe
            pipe_path = "/tmp/test_pipe"
            if not os.path.exists(pipe_path):
                os.mkfifo(pipe_path)
            
            # Try to read from pipe (will block until someone writes)
            with open(pipe_path, "r") as pipe_file:
                data = pipe_file.read()  # This will block forever
                
        except Exception as e:
            logger.error(f"File operation error: {e}")
            raise
    
    def simulate_thread_deadlock(self):
        """Simulate thread deadlock"""
        logger.info("Simulating thread deadlock...")
        
        lock1 = threading.Lock()
        lock2 = threading.Lock()
        
        def thread1():
            with lock1:
                time.sleep(0.1)
                with lock2:
                    pass
        
        def thread2():
            with lock2:
                time.sleep(0.1)
                with lock1:
                    pass
        
        # Start threads in opposite order to create deadlock
        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)
        
        t1.start()
        t2.start()
        
        # Wait for threads (will never complete due to deadlock)
        t1.join()
        t2.join()
    
    def simulate_subprocess_hang(self):
        """Simulate hanging subprocess call"""
        logger.info("Simulating subprocess hang...")
        
        # Start a subprocess that never exits
        import subprocess
        
        # Use a command that will hang
        process = subprocess.Popen(
            ["sleep", "3600"],  # Sleep for 1 hour
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for process (will hang for 1 hour)
        stdout, stderr = process.communicate()
        
        return stdout.decode()
    
    def setup_scenarios(self):
        """Set up all hanging scenarios"""
        scenarios = [
            HangingScenario(
                name="hanging_http_call",
                description="HTTP call without timeout (most common issue)",
                code_function=self.simulate_hanging_http_call,
                expected_hang_time=3600,  # 1 hour
                timeout_to_kill=30,  # Kill after 30 seconds
                symptoms=["High network I/O", "Process in sleep state", "No CPU usage"]
            ),
            HangingScenario(
                name="infinite_loop",
                description="Infinite while loop",
                code_function=self.simulate_infinite_loop,
                expected_hang_time=float('inf'),
                timeout_to_kill=10,
                symptoms=["High CPU usage", "No I/O", "Process running"]
            ),
            HangingScenario(
                name="database_lock_wait",
                description="Waiting for database lock",
                code_function=self.simulate_database_lock_wait,
                expected_hang_time=1800,  # 30 minutes
                timeout_to_kill=15,
                symptoms=["Database connections", "Process in sleep state", "Waiting for lock"]
            ),
            HangingScenario(
                name="full_disk_write",
                description="Writing to full disk",
                code_function=self.simulate_full_disk_write,
                expected_hang_time=300,  # 5 minutes
                timeout_to_kill=20,
                symptoms=["High disk I/O", "Disk space errors", "Process blocked"]
            ),
            HangingScenario(
                name="memory_leak",
                description="Memory leak causing swap",
                code_function=self.simulate_memory_leak,
                expected_hang_time=600,  # 10 minutes
                timeout_to_kill=15,
                symptoms=["Memory usage growing", "High swap usage", "Process slows down"]
            ),
            HangingScenario(
                name="blocking_file_operation",
                description="Blocking file read/write",
                code_function=self.simulate_blocking_file_operation,
                expected_hang_time=float('inf'),
                timeout_to_kill=10,
                symptoms=["Process in sleep state", "File handle open", "No CPU usage"]
            ),
            HangingScenario(
                name="thread_deadlock",
                description="Thread deadlock",
                code_function=self.simulate_thread_deadlock,
                expected_hang_time=float('inf'),
                timeout_to_kill=10,
                symptoms=["Multiple threads", "Process stuck", "No progress"]
            ),
            HangingScenario(
                name="subprocess_hang",
                description="Hanging subprocess call",
                code_function=self.simulate_subprocess_hang,
                expected_hang_time=3600,
                timeout_to_kill=15,
                symptoms=["Child process running", "Parent process waiting", "Zombie processes"]
            )
        ]
        
        for scenario in scenarios:
            self.register_scenario(scenario)
    
    def monitor_system_during_hang(self, duration: float) -> Dict[str, Any]:
        """
        Monitor system resources while a hang is occurring
        
        Args:
            duration: How long to monitor
            
        Returns:
            System monitoring data
        """
        monitoring_data = {
            'start_time': datetime.now().isoformat(),
            'duration': duration,
            'cpu_usage': [],
            'memory_usage': [],
            'disk_io': [],
            'network_io': [],
            'open_files': [],
            'threads': []
        }
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                # Collect metrics
                cpu_percent = self.current_process.cpu_percent()
                memory_info = self.current_process.memory_info()
                disk_io = self.current_process.io_counters()
                network_io = psutil.net_io_counters()
                
                monitoring_data['cpu_usage'].append(cpu_percent)
                monitoring_data['memory_usage'].append(memory_info.rss / 1024 / 1024)  # MB
                monitoring_data['disk_io'].append({
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes
                })
                monitoring_data['network_io'].append({
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv
                })
                monitoring_data['open_files'].append(len(self.current_process.open_files()))
                monitoring_data['threads'].append(self.current_process.num_threads())
                
                time.sleep(0.1)  # Monitor every 100ms
                
            except Exception as e:
                logger.error(f"Error monitoring system: {e}")
                break
        
        monitoring_data['end_time'] = datetime.now().isoformat()
        
        # Calculate statistics
        if monitoring_data['cpu_usage']:
            monitoring_data['avg_cpu'] = sum(monitoring_data['cpu_usage']) / len(monitoring_data['cpu_usage'])
            monitoring_data['max_cpu'] = max(monitoring_data['cpu_usage'])
        
        if monitoring_data['memory_usage']:
            monitoring_data['avg_memory_mb'] = sum(monitoring_data['memory_usage']) / len(monitoring_data['memory_usage'])
            monitoring_data['max_memory_mb'] = max(monitoring_data['memory_usage'])
        
        return monitoring_data
    
    def reproduce_scenario(self, scenario: HangingScenario) -> ReproductionResult:
        """
        Reproduce a specific hanging scenario
        
        Args:
            scenario: Scenario to reproduce
            
        Returns:
            Reproduction result
        """
        logger.info(f"Reproducing scenario: {scenario.name}")
        
        result = ReproductionResult(
            scenario_name=scenario.name,
            hung=False,
            hang_duration=0.0,
            timeout_triggered=False,
            error_message=None,
            stack_trace=None,
            system_impact={},
            timestamp=datetime.now().isoformat()
        )
        
        # Start system monitoring
        monitor_thread = threading.Thread(
            target=self.monitor_system_during_hang,
            args=(scenario.timeout_to_kill,),
            daemon=True
        )
        monitor_thread.start()
        
        start_time = time.time()
        
        try:
            # Use ThreadPoolExecutor with timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(scenario.code_function)
                
                try:
                    # Wait for completion with timeout
                    future.result(timeout=scenario.timeout_to_kill)
                    
                    # If we get here, the scenario didn't hang
                    result.hung = False
                    result.hang_duration = time.time() - start_time
                    
                except FutureTimeoutError:
                    # Scenario hung as expected
                    result.hung = True
                    result.hang_duration = time.time() - start_time
                    result.timeout_triggered = True
                    
                    logger.info(f"Scenario {scenario.name} hung as expected after {result.hang_duration:.2f}s")
                    
                    # Cancel the future
                    future.cancel()
                    
        except Exception as e:
            result.error_message = str(e)
            result.stack_trace = traceback.format_exc()
            logger.error(f"Error in scenario {scenario.name}: {e}")
        
        # Get system impact data
        try:
            # Get current system state
            result.system_impact = {
                'final_cpu_percent': self.current_process.cpu_percent(),
                'final_memory_mb': self.current_process.memory_info().rss / 1024 / 1024,
                'final_threads': self.current_process.num_threads(),
                'final_open_files': len(self.current_process.open_files()),
                'process_status': self.current_process.status()
            }
        except Exception as e:
            result.system_impact = {'error': str(e)}
        
        # Clean up any hanging resources
        self._cleanup_after_scenario(scenario)
        
        return result
    
    def _cleanup_after_scenario(self, scenario: HangingScenario):
        """Clean up resources after scenario reproduction"""
        try:
            # Kill any hanging subprocesses
            for child in self.current_process.children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            
            # Clean up temporary files
            temp_files = ["/tmp/large_file.log", "/tmp/test_pipe"]
            for temp_file in temp_files:
                try:
                    Path(temp_file).unlink(missing_ok=True)
                except:
                    pass
            
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def reproduce_all_scenarios(self) -> List[ReproductionResult]:
        """
        Reproduce all registered scenarios
        
        Returns:
            List of reproduction results
        """
        logger.info(f"Reproducing {len(self.scenarios)} scenarios...")
        
        results = []
        
        for scenario in self.scenarios:
            try:
                result = self.reproduce_scenario(scenario)
                results.append(result)
                
                # Brief pause between scenarios
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to reproduce scenario {scenario.name}: {e}")
                
                # Create error result
                error_result = ReproductionResult(
                    scenario_name=scenario.name,
                    hung=False,
                    hang_duration=0.0,
                    timeout_triggered=False,
                    error_message=str(e),
                    stack_trace=traceback.format_exc(),
                    system_impact={},
                    timestamp=datetime.now().isoformat()
                )
                results.append(error_result)
        
        self.results = results
        return results
    
    def analyze_results(self) -> Dict[str, Any]:
        """
        Analyze reproduction results
        
        Returns:
            Analysis summary
        """
        if not self.results:
            return {'error': 'No results to analyze'}
        
        analysis = {
            'total_scenarios': len(self.results),
            'successful_hangs': len([r for r in self.results if r.hung]),
            'failed_reproductions': len([r for r in self.results if r.error_message]),
            'scenarios_by_symptom': {},
            'most_likely_culprit': None,
            'recommendations': []
        }
        
        # Group by symptoms
        for scenario in self.scenarios:
            result = next((r for r in self.results if r.scenario_name == scenario.name), None)
            if result and result.hung:
                for symptom in scenario.symptoms:
                    if symptom not in analysis['scenarios_by_symptom']:
                        analysis['scenarios_by_symptom'][symptom] = []
                    analysis['scenarios_by_symptom'][symptom].append(scenario.name)
        
        # Identify most likely culprit based on common patterns
        hanging_results = [r for r in self.results if r.hung]
        if hanging_results:
            # HTTP hanging is most common in Airflow
            http_result = next((r for r in hanging_results if r.scenario_name == 'hanging_http_call'), None)
            if http_result:
                analysis['most_likely_culprit'] = {
                    'scenario': 'hanging_http_call',
                    'reason': 'Most common cause of stuck Airflow tasks',
                    'confidence': 0.8
                }
        
        # Generate recommendations
        if analysis['successful_hangs'] > 0:
            analysis['recommendations'].extend([
                "Add timeouts to all external HTTP calls",
                "Implement proper error handling for database operations",
                "Add monitoring for long-running tasks",
                "Use connection pooling for database connections",
                "Implement resource limits for tasks"
            ])
        
        return analysis
    
    def save_results(self, filename: Optional[str] = None):
        """Save reproduction results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bottleneck_reproduction_{timestamp}.json"
        
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'scenarios': [asdict(s) for s in self.scenarios],
                'results': [asdict(r) for r in self.results],
                'analysis': self.analyze_results()
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Results saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")


# CLI interface
def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bottleneck Reproduction Analysis")
    parser.add_argument("--scenario", help="Specific scenario to reproduce")
    parser.add_argument("--output", help="Output file for results")
    parser.add_argument("--list-scenarios", action="store_true", help="List available scenarios")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    reproducer = HangingCodeReproducer()
    reproducer.setup_scenarios()
    
    if args.list_scenarios:
        print("🔍 Available Scenarios:")
        for scenario in reproducer.scenarios:
            print(f"   - {scenario.name}: {scenario.description}")
            print(f"     Symptoms: {', '.join(scenario.symptoms)}")
        return
    
    try:
        if args.scenario:
            # Reproduce specific scenario
            scenario = next((s for s in reproducer.scenarios if s.name == args.scenario), None)
            if not scenario:
                print(f"❌ Scenario '{args.scenario}' not found")
                sys.exit(1)
            
            print(f"🔧 Reproducing scenario: {scenario.name}")
            result = reproducer.reproduce_scenario(scenario)
            
            print(f"\n📊 Result:")
            print(f"   Hung: {result.hung}")
            print(f"   Duration: {result.hang_duration:.2f}s")
            print(f"   Timeout Triggered: {result.timeout_triggered}")
            if result.error_message:
                print(f"   Error: {result.error_message}")
            
            reproducer.results = [result]
            
        else:
            # Reproduce all scenarios
            print("🔧 Reproducing all scenarios...")
            results = reproducer.reproduce_all_scenarios()
            
            print(f"\n📊 Results Summary:")
            for result in results:
                status = "🟢 HUNG" if result.hung else "🔴 FAILED" if result.error_message else "⚪ NO HANG"
                print(f"   {result.scenario_name}: {status} ({result.hang_duration:.2f}s)")
        
        # Analyze results
        analysis = reproducer.analyze_results()
        print(f"\n💡 Analysis:")
        print(f"   Total Scenarios: {analysis['total_scenarios']}")
        print(f"   Successful Hangs: {analysis['successful_hangs']}")
        print(f"   Failed Reproductions: {analysis['failed_reproductions']}")
        
        if analysis['most_likely_culprit']:
            culprit = analysis['most_likely_culprit']
            print(f"\n🎯 Most Likely Culprit: {culprit['scenario']}")
            print(f"   Reason: {culprit['reason']}")
            print(f"   Confidence: {culprit['confidence']:.1%}")
        
        if analysis['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in analysis['recommendations']:
                print(f"   - {rec}")
        
        # Save results
        reproducer.save_results(args.output)
        
    except KeyboardInterrupt:
        print("\n⏹️  Reproduction interrupted by user")
    except Exception as e:
        print(f"❌ Error during reproduction: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
