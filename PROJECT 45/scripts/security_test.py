#!/usr/bin/env python3
"""
Security Testing Script for JumpApp

This script performs comprehensive security testing to validate
that all security vulnerabilities have been properly fixed.
"""

import requests
import json
import time
import hashlib
import logging
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityTester:
    """Security testing suite for JumpApp."""
    
    def __init__(self, base_url='http://localhost:8000'):
        """
        Initialize security tester.
        
        Args:
            base_url: Base URL of the application
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SecurityTester/1.0'
        })
        
        # Test results
        self.test_results = {
            'sql_injection': [],
            'debug_endpoint': [],
            'csp_headers': [],
            's3_security': [],
            'password_security': [],
            'general_security': []
        }
        
        logger.info(f"Security tester initialized for {base_url}")
    
    def run_all_tests(self):
        """Run all security tests."""
        logger.info("Starting comprehensive security testing...")
        
        # Test SQL injection vulnerabilities
        self.test_sql_injection()
        
        # Test debug endpoint security
        self.test_debug_endpoint()
        
        # Test CSP headers
        self.test_csp_headers()
        
        # Test general security headers
        self.test_security_headers()
        
        # Test password security
        self.test_password_security()
        
        # Test access control
        self.test_access_control()
        
        # Test input validation
        self.test_input_validation()
        
        # Test rate limiting
        self.test_rate_limiting()
        
        # Test session security
        self.test_session_security()
        
        return self.test_results
    
    def test_sql_injection(self):
        """Test SQL injection vulnerabilities."""
        logger.info("Testing SQL injection vulnerabilities...")
        
        # SQL injection payloads
        sql_payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "' UNION SELECT * FROM auth_user --",
            "'; DROP TABLE jobs_job; --",
            "' OR 1=1 #",
            "admin'--",
            "' OR 'x'='x",
            "1' OR '1=1",
            "'; EXEC xp_cmdshell('dir'); --",
            "' UNION SELECT @@version --",
        ]
        
        # Test endpoints that might be vulnerable
        vulnerable_endpoints = [
            '/api/jobs/',
            '/jobs/search/',
            '/companies/',
            '/api/statistics/',
        ]
        
        for endpoint in vulnerable_endpoints:
            for payload in sql_payloads:
                try:
                    # Test GET parameter injection
                    response = self.session.get(
                        urljoin(self.base_url, endpoint),
                        params={'q': payload},
                        timeout=10
                    )
                    
                    # Check for SQL error messages
                    sql_errors = [
                        'syntax error',
                        'mysql_fetch',
                        'ORA-',
                        'Microsoft ODBC',
                        'PostgreSQL query failed',
                        'SQLSTATE',
                        'Warning: mysql',
                        'valid PostgreSQL',
                    ]
                    
                    content_lower = response.text.lower()
                    found_error = any(error.lower() in content_lower for error in sql_errors)
                    
                    if found_error:
                        self.test_results['sql_injection'].append({
                            'endpoint': endpoint,
                            'payload': payload,
                            'response_code': response.status_code,
                            'error_found': True,
                            'error_message': 'SQL error detected in response'
                        })
                        logger.error(f"SQL injection vulnerability found: {endpoint} with payload {payload}")
                    else:
                        self.test_results['sql_injection'].append({
                            'endpoint': endpoint,
                            'payload': payload,
                            'response_code': response.status_code,
                            'error_found': False
                        })
                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request failed for {endpoint}: {e}")
                    self.test_results['sql_injection'].append({
                        'endpoint': endpoint,
                        'payload': payload,
                        'error': str(e)
                    })
    
    def test_debug_endpoint(self):
        """Test debug endpoint security."""
        logger.info("Testing debug endpoint security...")
        
        debug_endpoints = [
            '/admin/debug/',
            '/debug/',
            '/__debug__/',
            '/admin/debug/info/',
        ]
        
        for endpoint in debug_endpoints:
            try:
                # Test without authentication
                response = self.session.get(urljoin(self.base_url, endpoint), timeout=10)
                
                is_vulnerable = (
                    response.status_code == 200 and
                    ('DEBUG' in response.text or
                     'settings' in response.text or
                     'SECRET_KEY' in response.text or
                     'DATABASE' in response.text)
                )
                
                self.test_results['debug_endpoint'].append({
                    'endpoint': endpoint,
                    'authenticated': False,
                    'response_code': response.status_code,
                    'vulnerable': is_vulnerable,
                    'content_length': len(response.text)
                })
                
                if is_vulnerable:
                    logger.error(f"Debug endpoint vulnerability found: {endpoint}")
                else:
                    logger.info(f"Debug endpoint secure: {endpoint}")
                
                # Test with fake authentication
                response = self.session.get(
                    urljoin(self.base_url, endpoint),
                    headers={'Authorization': 'Bearer fake_token'},
                    timeout=10
                )
                
                is_vulnerable_auth = response.status_code == 200
                
                self.test_results['debug_endpoint'].append({
                    'endpoint': endpoint,
                    'authenticated': True,
                    'response_code': response.status_code,
                    'vulnerable': is_vulnerable_auth,
                    'content_length': len(response.text)
                })
                
                if is_vulnerable_auth:
                    logger.error(f"Debug endpoint vulnerable with fake auth: {endpoint}")
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {endpoint}: {e}")
                self.test_results['debug_endpoint'].append({
                    'endpoint': endpoint,
                    'error': str(e)
                })
    
    def test_csp_headers(self):
        """Test Content Security Policy headers."""
        logger.info("Testing CSP headers...")
        
        try:
            response = self.session.get(self.base_url, timeout=10)
            
            csp_headers = [
                'Content-Security-Policy',
                'X-Content-Security-Policy',
                'X-WebKit-CSP'
            ]
            
            csp_found = False
            for header in csp_headers:
                if header in response.headers:
                    csp_found = True
                    csp_value = response.headers[header]
                    
                    # Check CSP directives
                    required_directives = [
                        'default-src',
                        'script-src',
                        'style-src',
                        'img-src'
                    ]
                    
                    missing_directives = []
                    for directive in required_directives:
                        if directive not in csp_value:
                            missing_directives.append(directive)
                    
                    self.test_results['csp_headers'].append({
                        'header': header,
                        'value': csp_value,
                        'missing_directives': missing_directives,
                        'secure': len(missing_directives) == 0
                    })
                    
                    if missing_directives:
                        logger.warning(f"CSP header {header} missing directives: {missing_directives}")
                    else:
                        logger.info(f"CSP header {header} properly configured")
            
            if not csp_found:
                self.test_results['csp_headers'].append({
                    'error': 'No CSP headers found',
                    'secure': False
                })
                logger.error("No CSP headers found")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to test CSP headers: {e}")
            self.test_results['csp_headers'].append({
                'error': str(e),
                'secure': False
            })
    
    def test_security_headers(self):
        """Test general security headers."""
        logger.info("Testing security headers...")
        
        try:
            response = self.session.get(self.base_url, timeout=10)
            
            security_headers = {
                'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
                'X-Content-Type-Options': ['nosniff'],
                'X-XSS-Protection': ['1; mode=block', '1'],
                'Strict-Transport-Security': ['max-age='],
                'Referrer-Policy': ['strict-origin-when-cross-origin', 'no-referrer'],
                'Permissions-Policy': None  # Any value is acceptable
            }
            
            for header, expected_values in security_headers.items():
                header_value = response.headers.get(header)
                
                if header_value:
                    if expected_values:
                        is_secure = any(expected in header_value for expected in expected_values)
                    else:
                        is_secure = True
                    
                    self.test_results['general_security'].append({
                        'header': header,
                        'value': header_value,
                        'secure': is_secure
                    })
                    
                    if is_secure:
                        logger.info(f"Security header {header} is secure")
                    else:
                        logger.warning(f"Security header {header} may not be secure: {header_value}")
                else:
                    self.test_results['general_security'].append({
                        'header': header,
                        'missing': True,
                        'secure': False
                    })
                    logger.warning(f"Security header {header} is missing")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to test security headers: {e}")
            self.test_results['general_security'].append({
                'error': str(e),
                'secure': False
            })
    
    def test_password_security(self):
        """Test password security."""
        logger.info("Testing password security...")
        
        # Test login endpoint
        login_endpoints = ['/login/', '/admin/login/', '/api/login/']
        
        for endpoint in login_endpoints:
            try:
                # Test with common weak passwords
                weak_passwords = [
                    'password',
                    '123456',
                    'admin',
                    'test',
                    'password123'
                ]
                
                for password in weak_passwords:
                    response = self.session.post(
                        urljoin(self.base_url, endpoint),
                        data={'username': 'admin', 'password': password},
                        timeout=10
                    )
                    
                    # Check if login succeeded (should not with weak passwords)
                    login_success = (
                        response.status_code == 302 or
                        'dashboard' in response.text.lower() or
                        'welcome' in response.text.lower()
                    )
                    
                    self.test_results['password_security'].append({
                        'endpoint': endpoint,
                        'password': password,
                        'response_code': response.status_code,
                        'login_success': login_success,
                        'vulnerable': login_success
                    })
                    
                    if login_success:
                        logger.error(f"Weak password accepted: {password} on {endpoint}")
                    else:
                        logger.info(f"Weak password rejected: {password} on {endpoint}")
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to test password security on {endpoint}: {e}")
                self.test_results['password_security'].append({
                    'endpoint': endpoint,
                    'error': str(e)
                })
    
    def test_access_control(self):
        """Test access control."""
        logger.info("Testing access control...")
        
        # Test protected endpoints
        protected_endpoints = [
            '/admin/',
            '/dashboard/',
            '/profile/',
            '/api/admin/',
            '/jobs/create/',
            '/companies/create/'
        ]
        
        for endpoint in protected_endpoints:
            try:
                # Test without authentication
                response = self.session.get(urljoin(self.base_url, endpoint), timeout=10)
                
                # Should redirect to login or return 403
                is_protected = (
                    response.status_code == 403 or
                    response.status_code == 401 or
                    'login' in response.url or
                    'signin' in response.url
                )
                
                self.test_results['general_security'].append({
                    'test': 'access_control',
                    'endpoint': endpoint,
                    'authenticated': False,
                    'response_code': response.status_code,
                    'protected': is_protected
                })
                
                if is_protected:
                    logger.info(f"Access control working: {endpoint}")
                else:
                    logger.warning(f"Access control may be weak: {endpoint}")
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to test access control on {endpoint}: {e}")
                self.test_results['general_security'].append({
                    'test': 'access_control',
                    'endpoint': endpoint,
                    'error': str(e)
                })
    
    def test_input_validation(self):
        """Test input validation."""
        logger.info("Testing input validation...")
        
        # Malicious payloads
        malicious_payloads = [
            '<script>alert("XSS")</script>',
            'javascript:alert("XSS")',
            '<img src=x onerror=alert("XSS")>',
            '"><script>alert("XSS")</script>',
            '${7*7}',
            '{{7*7}}',
            '../../../etc/passwd',
            'SELECT * FROM users',
            'UNION SELECT * FROM users',
            '<!--#exec cmd="ls" -->',
        ]
        
        # Test endpoints that accept user input
        input_endpoints = [
            '/jobs/search/',
            '/contact/',
            '/register/',
            '/api/jobs/',
        ]
        
        for endpoint in input_endpoints:
            for payload in malicious_payloads:
                try:
                    # Test GET parameter
                    response = self.session.get(
                        urljoin(self.base_url, endpoint),
                        params={'q': payload},
                        timeout=10
                    )
                    
                    # Check if payload is reflected in response
                    payload_reflected = payload in response.text
                    
                    self.test_results['general_security'].append({
                        'test': 'input_validation',
                        'endpoint': endpoint,
                        'payload': payload,
                        'method': 'GET',
                        'reflected': payload_reflected,
                        'vulnerable': payload_reflected
                    })
                    
                    if payload_reflected:
                        logger.warning(f"Input validation issue: {payload} reflected in {endpoint}")
                    else:
                        logger.info(f"Input validation working: {payload} not reflected in {endpoint}")
                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to test input validation on {endpoint}: {e}")
                    self.test_results['general_security'].append({
                        'test': 'input_validation',
                        'endpoint': endpoint,
                        'payload': payload,
                        'error': str(e)
                    })
    
    def test_rate_limiting(self):
        """Test rate limiting."""
        logger.info("Testing rate limiting...")
        
        # Test endpoint that should be rate limited
        rate_limit_endpoints = [
            '/api/login/',
            '/api/register/',
            '/api/password-reset/',
        ]
        
        for endpoint in rate_limit_endpoints:
            try:
                # Send multiple requests quickly
                responses = []
                for i in range(20):  # 20 requests
                    response = self.session.post(
                        urljoin(self.base_url, endpoint),
                        data={'username': 'test', 'password': 'test'},
                        timeout=5
                    )
                    responses.append(response)
                    time.sleep(0.1)  # 100ms between requests
                
                # Check if any responses are rate limited
                rate_limited = any(r.status_code == 429 for r in responses)
                
                self.test_results['general_security'].append({
                    'test': 'rate_limiting',
                    'endpoint': endpoint,
                    'requests_sent': len(responses),
                    'rate_limited': rate_limited,
                    'status_codes': [r.status_code for r in responses]
                })
                
                if rate_limited:
                    logger.info(f"Rate limiting working: {endpoint}")
                else:
                    logger.warning(f"Rate limiting may not be working: {endpoint}")
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to test rate limiting on {endpoint}: {e}")
                self.test_results['general_security'].append({
                    'test': 'rate_limiting',
                    'endpoint': endpoint,
                    'error': str(e)
                })
    
    def test_session_security(self):
        """Test session security."""
        logger.info("Testing session security...")
        
        try:
            # Login to get session
            login_response = self.session.post(
                urljoin(self.base_url, '/login/'),
                data={'username': 'test', 'password': 'test'},
                timeout=10
            )
            
            # Check session cookie security
            session_cookie = self.session.cookies.get('sessionid')
            
            if session_cookie:
                # Check cookie attributes
                secure_tests = {
                    'secure': session_cookie.secure if hasattr(session_cookie, 'secure') else False,
                    'httponly': session_cookie.has_nonstandard_attr('HttpOnly'),
                    'samesite': session_cookie.has_nonstandard_attr('SameSite')
                }
                
                self.test_results['general_security'].append({
                    'test': 'session_security',
                    'cookie_exists': True,
                    'secure_tests': secure_tests,
                    'secure': all(secure_tests.values())
                })
                
                if all(secure_tests.values()):
                    logger.info("Session security is properly configured")
                else:
                    logger.warning(f"Session security issues: {secure_tests}")
            else:
                self.test_results['general_security'].append({
                    'test': 'session_security',
                    'cookie_exists': False,
                    'secure': False
                })
                logger.warning("No session cookie found")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to test session security: {e}")
            self.test_results['general_security'].append({
                'test': 'session_security',
                'error': str(e),
                'secure': False
            })
    
    def generate_report(self):
        """Generate security test report."""
        report = {
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': self.base_url,
            'summary': {},
            'details': self.test_results
        }
        
        # Calculate summary
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        for category, tests in self.test_results.items():
            for test in tests:
                total_tests += 1
                if test.get('secure', True):
                    passed_tests += 1
                elif test.get('vulnerable', False) or test.get('error'):
                    failed_tests += 1
        
        report['summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }
        
        return report


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Security Testing for JumpApp')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL of the application')
    parser.add_argument('--output', help='Output file for test results')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize tester
    tester = SecurityTester(args.url)
    
    # Run tests
    logger.info("Starting security tests...")
    results = tester.run_all_tests()
    
    # Generate report
    report = tester.generate_report()
    
    # Print summary
    print("\n" + "="*50)
    print("SECURITY TEST RESULTS")
    print("="*50)
    
    print(f"Base URL: {report['base_url']}")
    print(f"Test Time: {report['test_timestamp']}")
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed_tests']}")
    print(f"Failed: {report['summary']['failed_tests']}")
    print(f"Pass Rate: {report['summary']['pass_rate']:.1f}%")
    
    # Print failed tests
    failed_tests = []
    for category, tests in results.items():
        for test in tests:
            if test.get('vulnerable', False) or test.get('error'):
                failed_tests.append({
                    'category': category,
                    'test': test
                })
    
    if failed_tests:
        print(f"\n🚨 FAILED TESTS ({len(failed_tests)}):")
        for i, failed_test in enumerate(failed_tests[:10], 1):  # Show first 10
            test = failed_test['test']
            category = failed_test['category']
            print(f"  {i}. [{category.upper()}] {test.get('endpoint', test.get('test', 'Unknown'))}")
            if test.get('error'):
                print(f"     Error: {test['error']}")
            elif test.get('vulnerable'):
                print(f"     Status: VULNERABLE")
    else:
        print("\n✅ All tests passed!")
    
    # Save results to file
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n💾 Results saved to {args.output}")
    
    print("\n" + "="*50)
    
    # Exit with appropriate code
    sys.exit(0 if report['summary']['failed_tests'] == 0 else 1)


if __name__ == '__main__':
    main()
