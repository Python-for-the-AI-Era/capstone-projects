#!/usr/bin/env python3
"""
Simple test to demonstrate the lxml dependency issue
"""

import subprocess
import sys

def test_current_environment():
    """Test current environment dependencies"""
    print("=== Testing Current Environment ===")
    
    try:
        # Test the import that commonly fails
        from bs4 import BeautifulSoup
        print("✅ BeautifulSoup import successful")
        
        import lxml
        print(f"✅ lxml version: {lxml.__version__}")
        
        # Test the problematic module
        try:
            from lxml.html import clean
            print("✅ lxml.html.clean module available")
        except ImportError as e:
            print(f"❌ lxml.html.clean module NOT available: {e}")
            print("This is the dependency issue!")
            return False
            
        # Test BeautifulSoup with lxml
        try:
            soup = BeautifulSoup("<html><body>Test</body></html>", 'lxml')
            print("✅ BeautifulSoup with lxml parser works")
        except Exception as e:
            print(f"❌ BeautifulSoup with lxml failed: {e}")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def show_pip_freeze():
    """Show current pip freeze output"""
    print("\n=== Current pip freeze ===")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "freeze"], 
                              capture_output=True, text=True)
        
        # Filter for relevant packages
        lines = result.stdout.split('\n')
        relevant = [line for line in lines if any(pkg in line.lower() 
                  for pkg in ['lxml', 'beautifulsoup', 'bs4', 'scrapy'])]
        
        for line in relevant:
            print(line)
            
    except Exception as e:
        print(f"Error getting pip freeze: {e}")

if __name__ == "__main__":
    show_pip_freeze()
    success = test_current_environment()
    
    if success:
        print("\n✅ All tests passed - dependencies are working correctly")
    else:
        print("\n❌ Tests failed - dependency issue detected")
