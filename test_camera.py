#!/usr/bin/env python3
"""
ArduCam 64MP Test and Verification Script

This script provides comprehensive testing and verification for the ArduCam 64MP
setup on Raspberry Pi 5. Use this to verify your camera is working before
running the main aircraft detection system.

Usage:
    python3 test_camera.py [--quick] [--save-images]

Options:
    --quick       : Run quick test only (single capture)
    --save-images : Save test images to disk
"""

import argparse
import subprocess
import cv2
import os
import time
import sys
from pathlib import Path

def check_system_requirements():
    """Check if system requirements are met"""
    print("🔍 Checking system requirements...")
    
    requirements = {
        'rpicam-hello': 'rpicam-apps package',
        'rpicam-still': 'rpicam-still command',
        'rpicam-vid': 'rpicam-vid command'
    }
    
    all_good = True
    for cmd, description in requirements.items():
        try:
            result = subprocess.run([cmd, '--help'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                print(f"  ✅ {description} - OK")
            else:
                print(f"  ❌ {description} - FAILED")
                all_good = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"  ❌ {description} - NOT FOUND")
            all_good = False
    
    return all_good

def check_camera_detection():
    """Check if ArduCam is detected by the system"""
    print("\n📷 Checking camera detection...")
    
    try:
        result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            if "arducam_64mp" in result.stdout:
                print("  ✅ ArduCam 64MP detected")
                
                # Extract camera info
                lines = result.stdout.split('\n')
                for line in lines:
                    if "arducam_64mp" in line:
                        print(f"  📋 {line.strip()}")
                return True
            else:
                print("  ❌ ArduCam 64MP NOT detected")
                print("  📋 Available cameras:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        print(f"      {line.strip()}")
                return False
        else:
            print(f"  ❌ Camera detection failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Camera detection timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error checking camera: {e}")
        return False

def check_camera_configuration():
    """Check camera configuration in config.txt"""
    print("\n⚙️  Checking camera configuration...")
    
    config_path = "/boot/firmware/config.txt"
    required_settings = {
        'camera_auto_detect': '0',
        'dtoverlay': 'arducam-64mp',
        'dtparam=i2c_vc': 'on',
        'gpu_mem': '128'
    }
    
    try:
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        found_settings = {}
        for line in config_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                for setting in required_settings:
                    if line.startswith(setting):
                        found_settings[setting] = line
        
        all_configured = True
        for setting, expected in required_settings.items():
            if setting in found_settings:
                if expected in found_settings[setting]:
                    print(f"  ✅ {setting}: {found_settings[setting]}")
                else:
                    print(f"  ⚠️  {setting}: {found_settings[setting]} (check value)")
                    all_configured = False
            else:
                print(f"  ❌ {setting}: NOT FOUND")
                all_configured = False
        
        return all_configured
        
    except Exception as e:
        print(f"  ❌ Error reading config: {e}")
        return False

def test_basic_capture(save_images=False):
    """Test basic camera capture functionality"""
    print("\n📸 Testing basic camera capture...")
    
    test_file = "/tmp/arducam_basic_test.jpg"
    
    try:
        # Test single capture
        result = subprocess.run([
            'rpicam-still', '-o', test_file,
            '--width', '1920', '--height', '1080',
            '--timeout', '3000', '--immediate'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(test_file):
            # Verify with OpenCV
            img = cv2.imread(test_file)
            if img is not None:
                print(f"  ✅ Basic capture successful: {img.shape}")
                
                if save_images:
                    save_path = f"test_basic_capture_{int(time.time())}.jpg"
                    cv2.imwrite(save_path, img)
                    print(f"  💾 Image saved as: {save_path}")
                
                # Clean up
                os.remove(test_file)
                return True
            else:
                print("  ❌ Cannot read captured image with OpenCV")
                return False
        else:
            print(f"  ❌ Capture failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Capture timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error during capture: {e}")
        return False

def test_autofocus():
    """Test autofocus functionality"""
    print("\n🎯 Testing autofocus...")
    
    try:
        # Test autofocus trigger
        result = subprocess.run([
            'rpicam-still', '-o', '/dev/null',
            '--autofocus-mode', 'auto',
            '--timeout', '3000'
        ], capture_output=True
