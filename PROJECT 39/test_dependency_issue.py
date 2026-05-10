#!/usr/bin/env python3
"""
Script to reproduce the lxml dependency issue
"""

import subprocess
import sys
import tempfile
import os

def test_broken_dependencies():
    """Test the broken dependency scenario"""
    print("=== Testing Broken Dependencies Scenario ===")
    
    # Create a temporary virtual environment
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = os.path.join(temp_dir, "test_venv")
        
        # Create virtual environment
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
        
        # Get pip path for the virtual environment
        if sys.platform == "win32":
            pip_path = os.path.join(venv_path, "Scripts", "pip")
            python_path = os.path.join(venv_path, "Scripts", "python")
        else:
            pip_path = os.path.join(venv_path, "bin", "pip")
            python_path = os.path.join(venv_path, "bin", "python")
        
        print("Installing broken dependencies...")
        # Install newer lxml that causes the issue
        subprocess.run([pip_path, "install", "lxml>=5.0.0", "beautifulsoup4>=4.12.0"], check=True)
        
        print("Testing import that should fail...")
        try:
            # This should fail with the broken dependency
            result = subprocess.run([
                python_path, "-c", 
                """
from bs4 import BeautifulSoup
import lxml
print('Import successful - this should not happen with broken deps')
"""
            ], capture_output=True, text=True, timeout=30)
            
            print(f"Exit code: {result.returncode}")
            if result.returncode != 0:
                print("ERROR OUTPUT:")
                print(result.stderr)
                return True  # Successfully reproduced the error
            else:
                print("Unexpected success - dependencies not broken")
                return False
                
        except subprocess.TimeoutExpired:
            print("Import test timed out")
            return True
        except Exception as e:
            print(f"Error during test: {e}")
            return True

def test_fixed_dependencies():
    """Test the fixed dependency scenario"""
    print("\n=== Testing Fixed Dependencies Scenario ===")
    
    # Create a temporary virtual environment
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = os.path.join(temp_dir, "test_venv_fixed")
        
        # Create virtual environment
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
        
        # Get pip path for the virtual environment
        if sys.platform == "win32":
            pip_path = os.path.join(venv_path, "Scripts", "pip")
            python_path = os.path.join(venv_path, "Scripts", "python")
        else:
            pip_path = os.path.join(venv_path, "bin", "pip")
            python_path = os.path.join(venv_path, "bin", "python")
        
        print("Installing fixed dependencies...")
        # Install the fixed versions
        subprocess.run([pip_path, "install", "lxml==4.9.4", "lxml-html-clean==0.1.0", "beautifulsoup4>=4.12.0"], check=True)
        
        print("Testing import that should work...")
        try:
            # This should work with the fixed dependencies
            result = subprocess.run([
                python_path, "-c", 
                """
from bs4 import BeautifulSoup
import lxml
print('Import successful - dependencies are fixed!')
"""
            ], capture_output=True, text=True, timeout=30)
            
            print(f"Exit code: {result.returncode}")
            if result.returncode == 0:
                print("SUCCESS OUTPUT:")
                print(result.stdout)
                return True  # Successfully fixed
            else:
                print("ERROR OUTPUT:")
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            print("Import test timed out")
            return False
        except Exception as e:
            print(f"Error during test: {e}")
            return False

def show_dependency_info():
    """Show current dependency information"""
    print("\n=== Current Environment Dependencies ===")
    
    try:
        import lxml
        print(f"lxml version: {lxml.__version__}")
    except ImportError:
        print("lxml not installed")
    
    try:
        import bs4
        print(f"beautifulsoup4 version: {bs4.__version__}")
    except ImportError:
        print("beautifulsoup4 not installed")
    
    # Try to import the problematic module
    try:
        from lxml.html import clean
        print("lxml.html.clean module: Available")
    except ImportError as e:
        print(f"lxml.html.clean module: NOT available - {e}")

if __name__ == "__main__":
    show_dependency_info()
    
    # Test the broken scenario
    broken_reproduced = test_broken_dependencies()
    
    # Test the fixed scenario
    fixed_works = test_fixed_dependencies()
    
    print(f"\n=== Summary ===")
    print(f"Broken scenario reproduced: {broken_reproduced}")
    print(f"Fixed scenario works: {fixed_works}")
