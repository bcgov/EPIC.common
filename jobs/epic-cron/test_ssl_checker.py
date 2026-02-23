#!/usr/bin/env python3
"""Simple test script for SSL checker functionality."""

import ssl
import socket
from datetime import datetime
from urllib.parse import urlparse
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def get_ssl_expiry_date(url):
    """Get SSL certificate expiry date using cryptography library."""
    try:
        # Parse URL
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.path
        port = parsed.port or 443
        
        # Create SSL context
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect and get certificate
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert_bin = ssock.getpeercert(binary_form=True)
                cert = x509.load_der_x509_certificate(cert_bin, default_backend())
                expiry_date = cert.not_valid_after_utc
                return expiry_date, None
                
    except socket.gaierror as e:
        return None, f"DNS resolution failed: {str(e)}"
    except socket.timeout:
        return None, "Connection timeout"
    except Exception as e:
        return None, f"Error: {type(e).__name__}: {str(e)}"

def calculate_ssl_status(expiry_date):
    """Calculate SSL status based on expiry date."""
    if not expiry_date:
        return "Unknown"
    
    # Use timezone-aware datetime for comparison
    from datetime import timezone
    now = datetime.now(timezone.utc)
    
    # Make sure expiry_date is timezone-aware
    if expiry_date.tzinfo is None:
        expiry_date = expiry_date.replace(tzinfo=timezone.utc)
    
    days_until_expiry = (expiry_date - now).days
    
    if days_until_expiry < 0:
        return "Expired"
    elif days_until_expiry <= 30:
        return "Expiring Soon"
    else:
        return "Valid"

# Run tests
print("Testing SSL Checker with cryptography library...")
print("=" * 60)

# Test 1: Valid SSL certificate
print("\n1. Testing valid SSL certificate (google.com):")
expiry, error = get_ssl_expiry_date("https://google.com")
if expiry:
    status = calculate_ssl_status(expiry)
    print(f"   ✓ Success! Expiry date: {expiry}")
    print(f"   Status: {status}")
else:
    print(f"   ✗ Error: {error}")

# Test 2: Another valid cert
print("\n2. Testing GitHub:")
expiry, error = get_ssl_expiry_date("https://github.com")
if expiry:
    status = calculate_ssl_status(expiry)
    print(f"   ✓ Success! Expiry date: {expiry}")
    print(f"   Status: {status}")
else:
    print(f"   ✗ Error: {error}")

# Test 3: Invalid hostname
print("\n3. Testing invalid hostname:")
expiry, error = get_ssl_expiry_date("https://thisdomaindoesnotexist12345.com")
if error:
    print(f"   ✓ Expected error: {error}")
else:
    print(f"   ✗ Unexpected success")

# Test 4: Non-HTTPS URL
print("\n4. Testing non-SSL URL (should fail):")
expiry, error = get_ssl_expiry_date("http://example.com")
if error:
    print(f"   ✓ Expected error: {error}")
else:
    print(f"   Certificate found (unexpected): {expiry}")

print("\n" + "=" * 60)
print("SSL Checker tests completed!")
