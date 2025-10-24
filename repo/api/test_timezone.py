#!/usr/bin/env python3
"""
Test timezone configuration in the container
"""
import os
from datetime import datetime
import pytz

def test_timezone():
    print("=== Timezone Configuration Test ===")
    
    # Check TZ environment variable
    tz_env = os.environ.get('TZ', 'Not set')
    print(f"TZ environment variable: {tz_env}")
    
    # Check system timezone
    try:
        with open('/etc/timezone', 'r') as f:
            system_tz = f.read().strip()
        print(f"System timezone: {system_tz}")
    except FileNotFoundError:
        print("System timezone: /etc/timezone not found")
    
    # Check current time in different ways
    print(f"Current UTC time: {datetime.utcnow()}")
    print(f"Current local time: {datetime.now()}")
    
    # Check with pytz if available
    try:
        toronto_tz = pytz.timezone('America/Toronto')
        toronto_time = datetime.now(toronto_tz)
        print(f"Toronto time (pytz): {toronto_time}")
        print(f"Toronto timezone: {toronto_time.tzinfo}")
    except ImportError:
        print("pytz not available for timezone testing")
    except Exception as e:
        print(f"Error with pytz: {e}")
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    test_timezone()
