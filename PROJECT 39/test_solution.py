#!/usr/bin/env python3
"""
Comprehensive test script to demonstrate the dependency issue and solution
"""

import subprocess
import sys
import tempfile
import os

def create_test_environment(env_name, requirements):
    """Create a temporary test environment with specific requirements"""
    temp_dir = tempfile.mkdtemp(prefix=f"test_{env_name}_")
    venv_path = os.path.join(temp_dir, "venv")
    
    # Create virtual environment
    subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, capture_output=True)
    
    # Get pip and python paths
    if sys.platform == "win32":
        pip_path = os.path.join(venv_path, "Scripts", "pip")
        python_path = os.path.join(venv_path, "Scripts", "python")
    else:
        pip_path = os.path.join(venv_path, "bin", "pip")
        python_path = os.path.join(venv_path, "bin", "python")
    
    # Install requirements
    print(f"Installing requirements for {env_name}...")
    try:
        subprocess.run([pip_path, "install"] + requirements, check=True, capture_output=True)
        return python_path, pip_path
    except subprocess.CalledProcessError as e:
        print(f"Failed to install requirements: {e}")
        print(f"STDERR: {e.stderr.decode() if e.stderr else 'No stderr'}")
        return None, None

def test_environment(python_path, env_name):
    """Test if the environment works correctly"""
    if not python_path:
        return False
    
    print(f"Testing {env_name}...")
    
    test_script = """
try:
    from bs4 import BeautifulSoup
    import lxml
    from lxml.html import clean
    print("SUCCESS: All imports work correctly")
    
    # Test actual functionality
    soup = BeautifulSoup("<html><body>Test</body></html>", 'lxml')
    print("SUCCESS: BeautifulSoup with lxml parser works")
    
    print(f"lxml version: {lxml.__version__}")
    exit(0)
except ImportError as e:
    print(f"FAILED: Import error - {e}")
    exit(1)
except Exception as e:
    print(f"FAILED: Runtime error - {e}")
    exit(1)
"""
    
    try:
        result = subprocess.run([python_path, "-c", test_script], 
                              capture_output=True, text=True, timeout=30)
        
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Errors: {result.stderr}")
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("FAILED: Test timed out")
        return False
    except Exception as e:
        print(f"FAILED: Test error - {e}")
        return False

def main():
    print("=== Dependency Issue Demonstration and Solution ===\n")
    
    # Test 1: Broken environment (simulating the original issue)
    print("1. Testing BROKEN environment (simulating original issue)")
    broken_requirements = ["Scrapy>=2.11.0", "beautifulsoup4>=4.12.0", "lxml>=5.0.0"]
    broken_python, broken_pip = create_test_environment("broken", broken_requirements)
    
    if broken_python:
        broken_works = test_environment(broken_python, "broken")
        print(f"Broken environment result: {'✅ WORKS' if broken_works else '❌ FAILS'}")
    else:
        print("❌ Failed to create broken environment (expected due to lxml 5.0+ issues)")
    
    print("\n" + "="*60 + "\n")
    
    # Test 2: Fixed environment
    print("2. Testing FIXED environment (our solution)")
    fixed_requirements = [
        "Scrapy>=2.11.0", 
        "beautifulsoup4>=4.12.0", 
        "lxml>=4.9.0,<5.0.0",
        "lxml-html-clean>=0.1.0"
    ]
    fixed_python, fixed_pip = create_test_environment("fixed", fixed_requirements)
    
    if fixed_python:
        fixed_works = test_environment(fixed_python, "fixed")
        print(f"Fixed environment result: {'✅ WORKS' if fixed_works else '❌ FAILS'}")
    else:
        print("❌ Failed to create fixed environment")
    
    print("\n" + "="*60 + "\n")
    
    # Test 3: Show current environment
    print("3. Current environment status")
    try:
        import bs4
        print(f"✅ BeautifulSoup4 version: {bs4.__version__}")
    except ImportError:
        print("❌ BeautifulSoup4 not installed")
    
    try:
        import lxml
        print(f"✅ lxml version: {lxml.__version__}")
        
        try:
            from lxml.html import clean
            print("✅ lxml.html.clean module available")
        except ImportError:
            print("❌ lxml.html.clean module NOT available")
    except ImportError:
        print("❌ lxml not installed")
    
    print("\n" + "="*60)
    print("SUMMARY:")
    print("The issue occurs when lxml 5.0+ is installed without lxml-html-clean")
    print("Our solution pins lxml to <5.0.0 and includes lxml-html-clean")
    print("This ensures compatibility across different environments")

if __name__ == "__main__":
    main()
