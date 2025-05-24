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
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            print("  ✅ Autofocus test successful")
            return True
        else:
            print(f"  ⚠️  Autofocus test failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Autofocus test timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error testing autofocus: {e}")
        return False

def test_high_resolution(save_images=False):
    """Test high resolution capture"""
    print("\n📐 Testing high resolution capture...")
    
    test_file = "/tmp/arducam_highres_test.jpg"
    
    try:
        # Test high-res capture (4K)
        result = subprocess.run([
            'rpicam-still', '-o', test_file,
            '--width', '3840', '--height', '2160',
            '--timeout', '5000', '--quality', '95'
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and os.path.exists(test_file):
            img = cv2.imread(test_file)
            if img is not None:
                file_size = os.path.getsize(test_file)
                print(f"  ✅ High-res capture successful: {img.shape} ({file_size:,} bytes)")
                
                if save_images:
                    save_path = f"test_highres_{int(time.time())}.jpg"
                    cv2.imwrite(save_path, img)
                    print(f"  💾 High-res image saved as: {save_path}")
                
                os.remove(test_file)
                return True
            else:
                print("  ❌ Cannot read high-res image with OpenCV")
                return False
        else:
            print(f"  ❌ High-res capture failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ High-res capture timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error during high-res capture: {e}")
        return False

def test_video_mode():
    """Test video recording capability"""
    print("\n🎥 Testing video recording...")
    
    test_file = "/tmp/arducam_video_test.h264"
    
    try:
        # Test 5-second video
        result = subprocess.run([
            'rpicam-vid', '-t', '5000', '-o', test_file,
            '--width', '1920', '--height', '1080'
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and os.path.exists(test_file):
            file_size = os.path.getsize(test_file)
            if file_size > 1000:  # Should be more than 1KB for 5 seconds
                print(f"  ✅ Video recording successful ({file_size:,} bytes)")
                os.remove(test_file)
                return True
            else:
                print("  ❌ Video file too small or empty")
                return False
        else:
            print(f"  ❌ Video recording failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Video recording timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error during video recording: {e}")
        return False

def test_arducam_module():
    """Test the ArduCam Python module"""
    print("\n🐍 Testing ArduCam Python module...")
    
    try:
        # Try to import and test the module
        from arducam_camera import ArduCam64MP
        
        camera = ArduCam64MP(resolution=(1280, 720))
        
        if camera.initialize():
            print("  ✅ ArduCam module initialization successful")
            
            # Test single frame capture
            frame = camera.capture_frame()
            if frame is not None:
                print(f"  ✅ Module frame capture successful: {frame.shape}")
                camera.release()
                return True
            else:
                print("  ❌ Module frame capture failed")
                camera.release()
                return False
        else:
            print("  ❌ ArduCam module initialization failed")
            return False
            
    except ImportError as e:
        print(f"  ❌ Cannot import ArduCam module: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error testing ArduCam module: {e}")
        return False

def print_troubleshooting_tips():
    """Print troubleshooting tips for common issues"""
    print("\n🔧 TROUBLESHOOTING TIPS")
    print("="*50)
    
    tips = [
        ("Camera not detected", [
            "Check camera cable connection (silver contacts face Ethernet port on Pi 5)",
            "Verify camera is properly seated in connector",
            "Check /boot/firmware/config.txt has correct settings",
            "Reboot after making config changes"
        ]),
        
        ("'No cameras available' error", [
            "Ensure camera_auto_detect=0 in config.txt",
            "Use dtoverlay=arducam-64mp,cam0 (cam0 for Pi 5)",
            "Check gpu_mem=128 is set",
            "Verify no other processes using camera"
        ]),
        
        ("Pipeline handler errors", [
            "Kill any rpicam processes: sudo pkill -f rpicam",
            "Only run one camera application at a time",
            "Restart if camera gets stuck"
        ]),
        
        ("Image quality issues", [
            "Clean camera lens",
            "Test autofocus functionality",
            "Adjust lighting conditions",
            "Try manual focus settings"
        ])
    ]
    
    for issue, solutions in tips:
        print(f"\n❓ {issue}:")
        for solution in solutions:
            print(f"   • {solution}")

def main():
    parser = argparse.ArgumentParser(description='ArduCam 64MP Test Script')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick test only')
    parser.add_argument('--save-images', action='store_true',
                       help='Save test images to disk')
    
    args = parser.parse_args()
    
    print("🚀 ArduCam 64MP Test Script")
    print("="*50)
    print("This script will test your ArduCam setup comprehensively")
    print()
    
    # Track test results
    tests = []
    
    # System requirements check
    tests.append(("System Requirements", check_system_requirements()))
    
    # Camera detection
    tests.append(("Camera Detection", check_camera_detection()))
    
    # Configuration check
    tests.append(("Configuration", check_camera_configuration()))
    
    # Basic capture test
    tests.append(("Basic Capture", test_basic_capture(save_images=args.save_images)))
    
    if not args.quick:
        # Extended tests
        tests.append(("Autofocus", test_autofocus()))
        tests.append(("High Resolution", test_high_resolution(save_images=args.save_images)))
        tests.append(("Video Recording", test_video_mode()))
        tests.append(("Python Module", test_arducam_module()))
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} : {status}")
        if result:
            passed += 1
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("Your ArduCam 64MP is ready for aircraft detection!")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("Please check the failures above and refer to troubleshooting tips")
        print_troubleshooting_tips()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
