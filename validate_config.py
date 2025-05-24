#!/usr/bin/env python3
"""
Configuration Validator for Raspberry Pi 5 + ArduCam 64MP

This script validates and optionally fixes the configuration for the ArduCam 64MP
on Raspberry Pi 5. It checks config.txt settings and provides recommendations.

Usage:
    python3 validate_config.py [--fix] [--backup]

Options:
    --fix    : Automatically fix configuration issues
    --backup : Create backup before making changes
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CONFIG_PATH = "/boot/firmware/config.txt"
BACKUP_DIR = "/boot/firmware/backups"

REQUIRED_CONFIG = {
    'camera_auto_detect': '0',
    'dtoverlay': 'arducam-64mp,cam0',
    'dtparam=i2c_vc': 'on',
    'gpu_mem': '128'
}

RECOMMENDED_CONFIG = {
    'dtparam=i2c_arm': 'on',
    'dtparam=spi': 'on'
}

def check_pi_model():
    """Check if this is a Raspberry Pi 5"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip()
        
        if 'Raspberry Pi 5' in model:
            print(f"✅ Detected: {model}")
            return True
        else:
            print(f"⚠️  Warning: This script is for Pi 5, detected: {model}")
            return False
    except Exception as e:
        print(f"❌ Could not detect Pi model: {e}")
        return False

def backup_config():
    """Create backup of current config.txt"""
    try:
        # Create backup directory
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{BACKUP_DIR}/config_backup_{timestamp}.txt"
        
        shutil.copy2(CONFIG_PATH, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None

def read_config():
    """Read and parse current config.txt"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            lines = f.readlines()
        
        config = {}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                if '=' in stripped:
                    key, value = stripped.split('=', 1)
                    config[key] = value
                else:
                    # Handle lines without '=' (like dtoverlay)
                    config[stripped] = ''
        
        return lines, config
    except Exception as e:
        print(f"❌ Failed to read config: {e}")
        return None, None

def validate_config():
    """Validate current configuration"""
    print("🔍 Validating configuration...")
    
    lines, current_config = read_config()
    if current_config is None:
        return False, []
    
    issues = []
    recommendations = []
    
    # Check required settings
    for setting, expected_value in REQUIRED_CONFIG.items():
        found = False
        correct_value = False
        
        # Check exact match first
        if setting in current_config:
            found = True
            if expected_value in current_config[setting] or current_config[setting] == expected_value:
                correct_value = True
                print(f"  ✅ {setting}: {current_config[setting]}")
            else:
                print(f"  ⚠️  {setting}: {current_config[setting]} (expected: {expected_value})")
                issues.append(('incorrect_value', setting, expected_value, current_config[setting]))
        else:
            # Check for partial matches (e.g., dtoverlay variations)
            for key in current_config.keys():
                if setting.split('=')[0] in key:
                    found = True
                    if expected_value in current_config[key]:
                        correct_value = True
                        print(f"  ✅ {key}: {current_config[key]}")
                    else:
                        print(f"  ⚠️  {key}: {current_config[key]} (expected: {expected_value})")
                        issues.append(('incorrect_value', setting, expected_value, current_config[key]))
                    break
        
        if not found:
            print(f"  ❌ {setting}: NOT FOUND")
            issues.append(('missing', setting, expected_value, None))
    
    # Check recommended settings
    print("\n📋 Recommended settings:")
    for setting, expected_value in RECOMMENDED_CONFIG.items():
        if setting in current_config:
            if expected_value in current_config[setting]:
                print(f"  ✅ {setting}: {current_config[setting]}")
            else:
                print(f"  💡 {setting}: {current_config[setting]} (recommend: {expected_value})")
                recommendations.append(('recommend', setting, expected_value, current_config[setting]))
        else:
            print(f"  💡 {setting}: NOT SET (recommend: {expected_value})")
            recommendations.append(('recommend', setting, expected_value, None))
    
    # Check for conflicting settings
    print("\n🔍 Checking for conflicts...")
    conflicts = []
    
    # Check for camera_auto_detect=1 (conflicts with manual overlay)
    if 'camera_auto_detect' in current_config:
        if current_config['camera_auto_detect'] == '1':
            conflicts.append("camera_auto_detect=1 conflicts with manual dtoverlay")
    
    # Check for old-style overlays
    for key in current_config.keys():
        if 'dtoverlay' in key and 'imx477' in current_config[key]:
            conflicts.append(f"Old overlay detected: {key}={current_config[key]}")
    
    if conflicts:
        for conflict in conflicts:
            print(f"  ⚠️  {conflict}")
            issues.append(('conflict', conflict, None, None))
    else:
        print("  ✅ No conflicts detected")
    
    return len(issues) == 0, issues + recommendations

def fix_config(issues, backup_path=None):
    """Fix configuration issues"""
    if not issues:
        print("✅ No fixes needed")
        return True
    
    print(f"\n🔧 Applying {len(issues)} fixes...")
    
    try:
        lines, current_config = read_config()
        if lines is None:
            return False
        
        # Apply fixes
        new_lines = lines.copy()
        changes_made = []
        
        for issue_type, setting, expected, current in issues:
            if issue_type == 'missing':
                # Add missing setting
                if setting.startswith('dtoverlay'):
                    line_to_add = f"{setting}\n"
                else:
                    line_to_add = f"{setting}={expected}\n"
                
                # Find a good place to insert (near other similar settings)
                insert_index = len(new_lines)
                for i, line in enumerate(new_lines):
                    if setting.split('=')[0] in line or 'camera' in line.lower():
                        insert_index = i + 1
                        break
                
                new_lines.insert(insert_index, line_to_add)
                changes_made.append(f"Added: {line_to_add.strip()}")
                
            elif issue_type == 'incorrect_value':
                # Fix incorrect value
                for i, line in enumerate(new_lines):
                    if setting in line and not line.strip().startswith('#'):
                        if setting.startswith('dtoverlay'):
                            new_lines[i] = f"{setting}\n"
                        else:
                            new_lines[i] = f"{setting}={expected}\n"
                        changes_made.append(f"Changed: {line.strip()} -> {new_lines[i].strip()}")
                        break
                        
            elif issue_type == 'conflict':
                # Handle conflicts
                if 'camera_auto_detect=1' in setting:
                    for i, line in enumerate(new_lines):
                        if 'camera_auto_detect=1' in line:
                            new_lines[i] = 'camera_auto_detect=0\n'
                            changes_made.append(f"Fixed conflict: {line.strip()} -> camera_auto_detect=0")
                            break
        
        # Write new configuration
        with open(CONFIG_PATH, 'w') as f:
            f.writelines(new_lines)
        
        print("✅ Configuration updated successfully")
        print("\n📝 Changes made:")
        for change in changes_made:
            print(f"  • {change}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to fix configuration: {e}")
        if backup_path:
            print(f"💾 Restoring backup from: {backup_path}")
            try:
                shutil.copy2(backup_path, CONFIG_PATH)
                print("✅ Backup restored")
            except:
                print("❌ Failed to restore backup")
        return False

def test_configuration():
    """Test if the camera works with current configuration"""
    print("\n🧪 Testing camera with current configuration...")
    
    try:
        # Test camera detection
        result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            if 'arducam_64mp' in result.stdout:
                print("  ✅ Camera detected successfully")
                
                # Test basic capture
                test_result = subprocess.run([
                    'rpicam-still', '-o', '/tmp/config_test.jpg',
                    '--timeout', '3000', '--width', '640', '--height', '480'
                ], capture_output=True, text=True, timeout=10)
                
                if test_result.returncode == 0:
                    print("  ✅ Camera capture test successful")
                    try:
                        os.remove('/tmp/config_test.jpg')
                    except:
                        pass
                    return True
                else:
                    print(f"  ❌ Camera capture failed: {test_result.stderr}")
                    return False
            else:
                print("  ❌ ArduCam 64MP not detected")
                print("  📋 Available cameras:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        print(f"      {line.strip()}")
                return False
        else:
            print(f"  ❌ Camera detection failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Camera test timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error testing camera: {e}")
        return False

def print_next_steps():
    """Print next steps for the user"""
    print("\n🚀 NEXT STEPS")
    print("="*50)
    print("1. Reboot your Raspberry Pi:")
    print("   sudo reboot")
    print()
    print("2. After reboot, test the camera:")
    print("   python3 test_camera.py")
    print()
    print("3. Run the aircraft detection system:")
    print("   python3 pi-aircraft-detector.py --web")
    print()
    print("4. Access web interface:")
    print("   http://192.168.1.243:8080")

def main():
    parser = argparse.ArgumentParser(description='Validate ArduCam configuration')
    parser.add_argument('--fix', action='store_true',
                       help='Automatically fix configuration issues')
    parser.add_argument('--backup', action='store_true',
                       help='Create backup before making changes')
    
    args = parser.parse_args()
    
    print("🔧 ArduCam 64MP Configuration Validator")
    print("="*50)
    
    # Check if running as root for config changes
    if args.fix and os.geteuid() != 0:
        print("❌ Root privileges required for --fix option")
        print("   Run with: sudo python3 validate_config.py --fix")
        return 1
    
    # Check Pi model
    if not check_pi_model():
        print("⚠️  Continuing anyway...")
    
    # Check if config file exists
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Config file not found: {CONFIG_PATH}")
        return 1
    
    # Validate current configuration
    is_valid, issues = validate_config()
    
    if is_valid:
        print("\n🎉 Configuration is valid!")
        
        # Test camera functionality
        if test_configuration():
            print("\n✅ Camera is working correctly!")
        else:
            print("\n⚠️  Configuration looks correct but camera test failed")
            print("   You may need to reboot or check hardware connections")
    else:
        print(f"\n⚠️  Found {len(issues)} configuration issues")
        
        if args.fix:
            # Create backup if requested
            backup_path = None
            if args.backup:
                backup_path = backup_config()
            
            # Fix issues
            if fix_config(issues, backup_path):
                print("\n✅ Configuration fixed successfully!")
                print_next_steps()
            else:
                print("\n❌ Failed to fix configuration")
                return 1
        else:
            print("\n💡 Run with --fix to automatically fix these issues:")
            print("   sudo python3 validate_config.py --fix --backup")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
