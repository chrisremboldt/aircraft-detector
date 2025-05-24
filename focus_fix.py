#!/usr/bin/env python3
"""
ArduCam 64MP Focus Diagnostic and Fix Script

This script helps diagnose and fix focus issues with the ArduCam 64MP camera
specifically for aircraft detection applications requiring infinity focus.

Usage:
    python3 focus_fix.py --test        # Test current focus
    python3 focus_fix.py --fix         # Fix focus for aircraft detection
    python3 focus_fix.py --interactive # Interactive focus adjustment
    python3 focus_fix.py --verify      # Verify focus quality
"""

import subprocess
import argparse
import time
import os
import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_current_focus():
    """Test the current focus setting and quality"""
    print("🔍 Testing current camera focus...")
    
    test_file = f"focus_test_{int(time.time())}.jpg"
    
    try:
        # Test with current system settings
        result = subprocess.run([
            'rpicam-still', '-o', test_file,
            '--timeout', '3000',
            '--nopreview', '1'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(test_file):
            # Analyze focus quality
            image = cv2.imread(test_file)
            if image is not None:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                print(f"📊 Focus Quality Analysis:")
                print(f"   • Image captured: {image.shape}")
                print(f"   • Laplacian variance: {laplacian_var:.1f}")
                
                if laplacian_var > 300:
                    print("   ✅ Excellent focus quality")
                elif laplacian_var > 100:
                    print("   ✅ Good focus quality - suitable for aircraft detection")
                elif laplacian_var > 50:
                    print("   ⚠️  Fair focus quality - may need adjustment")
                else:
                    print("   ❌ Poor focus quality - definitely needs fixing")
                
                # Clean up
                os.remove(test_file)
                return laplacian_var
            else:
                print("❌ Could not read captured image")
                return 0
        else:
            print(f"❌ Camera capture failed: {result.stderr}")
            return 0
            
    except Exception as e:
        print(f"❌ Focus test failed: {e}")
        return 0

def fix_infinity_focus():
    """Fix the camera focus for infinity (aircraft detection)"""
    print("🔧 Fixing camera focus for aircraft detection (infinity focus)...")
    
    methods = [
        {
            "name": "Method 1: Direct infinity focus",
            "args": [
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'manual',
                '--lens-position', '0.0',
                '--timeout', '3000',
                '--nopreview', '1'
            ]
        },
        {
            "name": "Method 2: Autofocus then manual lock",
            "args": [
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'auto',
                '--autofocus-range', 'normal',
                '--timeout', '5000',
                '--nopreview', '1'
            ]
        },
        {
            "name": "Method 3: Continuous autofocus with normal range",
            "args": [
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'continuous',
                '--autofocus-range', 'normal',
                '--timeout', '3000',
                '--nopreview', '1'
            ]
        }
    ]
    
    for method in methods:
        print(f"\n🔄 Trying {method['name']}...")
        try:
            result = subprocess.run(method['args'], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f"   ✅ {method['name']} completed successfully")
                
                # Test the focus quality after this method
                print("   📊 Testing focus quality...")
                quality = test_current_focus()
                if quality > 100:
                    print(f"   🎯 Focus fixed! Quality score: {quality:.1f}")
                    return True
                else:
                    print(f"   ⚠️  Focus needs more adjustment. Score: {quality:.1f}")
            else:
                print(f"   ❌ {method['name']} failed: {result.stderr}")
        except Exception as e:
            print(f"   ❌ {method['name']} exception: {e}")
    
    print("\n⚠️  Automatic focus fix attempts completed. Try interactive mode for manual adjustment.")
    return False

def interactive_focus():
    """Interactive focus adjustment"""
    print("🎮 Interactive Focus Adjustment Mode")
    print("This will help you manually find the best focus for aircraft detection.")
    print("\nInstructions:")
    print("- We'll test different focus positions")
    print("- Focus positions are in dioptres (0.0 = infinity, higher = closer)")
    print("- For aircraft detection, you want 0.0 or very close to it")
    print("- Press Ctrl+C to exit at any time")
    
    focus_positions = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0]
    best_focus = 0.0
    best_quality = 0
    
    try:
        for pos in focus_positions:
            print(f"\n🔍 Testing focus position {pos} dioptres...")
            
            test_file = f"focus_test_{pos}_{int(time.time())}.jpg"
            
            # Set focus and capture
            result = subprocess.run([
                'rpicam-still', '-o', test_file,
                '--autofocus-mode', 'manual',
                '--lens-position', str(pos),
                '--timeout', '3000',
                '--nopreview', '1'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists(test_file):
                # Analyze quality
                image = cv2.imread(test_file)
                if image is not None:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                    
                    distance_str = "infinity" if pos == 0.0 else f"~{1.0/pos:.1f}m"
                    print(f"   📊 Position {pos} ({distance_str}): Quality = {laplacian_var:.1f}")
                    
                    if laplacian_var > best_quality:
                        best_quality = laplacian_var
                        best_focus = pos
                        print(f"   🎯 New best focus found!")
                    
                    # Save the image with focus info in filename
                    labeled_file = f"focus_test_pos_{pos}_quality_{laplacian_var:.0f}.jpg"
                    os.rename(test_file, labeled_file)
                    print(f"   💾 Saved as {labeled_file}")
                else:
                    print(f"   ❌ Could not read image for position {pos}")
            else:
                print(f"   ❌ Capture failed for position {pos}")
        
        print(f"\n🏆 RESULTS:")
        print(f"   Best focus position: {best_focus} dioptres")
        print(f"   Best quality score: {best_quality:.1f}")
        distance_str = "infinity" if best_focus == 0.0 else f"~{1.0/best_focus:.1f}m"
        print(f"   Focus distance: {distance_str}")
        
        if best_focus <= 0.2:
            print("   ✅ Excellent for aircraft detection!")
        else:
            print("   ⚠️  Focus may be too close for optimal aircraft detection")
        
        # Set the best focus
        print(f"\n🔧 Setting camera to best focus position ({best_focus})...")
        subprocess.run([
            'rpicam-still', '-o', '/dev/null',
            '--autofocus-mode', 'manual',
            '--lens-position', str(best_focus),
            '--timeout', '2000',
            '--nopreview', '1'
        ], capture_output=True, timeout=5)
        
        print("✅ Focus adjustment complete!")
        
    except KeyboardInterrupt:
        print("\n⏸️  Interactive focus adjustment stopped by user")
    except Exception as e:
        print(f"\n❌ Interactive focus failed: {e}")

def verify_focus():
    """Verify current focus is suitable for aircraft detection"""
    print("✅ Verifying focus for aircraft detection...")
    
    # Take multiple test shots and analyze
    qualities = []
    
    for i in range(3):
        print(f"   📸 Taking test shot {i+1}/3...")
        
        test_file = f"verify_{i}_{int(time.time())}.jpg"
        
        result = subprocess.run([
            'rpicam-still', '-o', test_file,
            '--timeout', '2000',
            '--nopreview', '1'
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0 and os.path.exists(test_file):
            image = cv2.imread(test_file)
            if image is not None:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                qualities.append(laplacian_var)
                print(f"      Quality: {laplacian_var:.1f}")
            os.remove(test_file)
        
        time.sleep(1)
    
    if qualities:
        avg_quality = np.mean(qualities)
        std_quality = np.std(qualities)
        
        print(f"\n📊 Focus Verification Results:")
        print(f"   Average quality: {avg_quality:.1f}")
        print(f"   Consistency (std): {std_quality:.1f}")
        
        if avg_quality > 200:
            print("   🎯 EXCELLENT - Perfect for aircraft detection!")
        elif avg_quality > 100:
            print("   ✅ GOOD - Suitable for aircraft detection")
        elif avg_quality > 50:
            print("   ⚠️  FAIR - May need fine-tuning for optimal results")
        else:
            print("   ❌ POOR - Focus definitely needs fixing")
            
        if std_quality < 20:
            print("   🔒 Focus is stable and consistent")
        else:
            print("   ⚠️  Focus consistency could be improved")
            
        return avg_quality > 100
    else:
        print("❌ Could not verify focus - all test shots failed")
        return False

def main():
    parser = argparse.ArgumentParser(description='ArduCam 64MP Focus Diagnostic and Fix Tool')
    parser.add_argument('--test', action='store_true', help='Test current focus quality')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix focus for aircraft detection')
    parser.add_argument('--interactive', action='store_true', help='Interactive focus adjustment')
    parser.add_argument('--verify', action='store_true', help='Verify focus is suitable for aircraft detection')
    parser.add_argument('--all', action='store_true', help='Run all tests and fixes')
    
    args = parser.parse_args()
    
    if not any([args.test, args.fix, args.interactive, args.verify, args.all]):
        parser.print_help()
        return
    
    print("🎯 ArduCam 64MP Focus Diagnostic Tool")
    print("=" * 50)
    
    # Check if camera is detected
    print("🔍 Checking camera detection...")
    try:
        result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Camera detected successfully")
            if 'arducam' in result.stdout.lower() or '64mp' in result.stdout.lower():
                print("✅ ArduCam 64MP identified")
            else:
                print("⚠️  Camera detected but not clearly identified as ArduCam 64MP")
        else:
            print("❌ Camera not detected - check connections and drivers")
            return
    except Exception as e:
        print(f"❌ Camera detection failed: {e}")
        return
    
    if args.test or args.all:
        print("\n" + "="*50)
        test_current_focus()
    
    if args.fix or args.all:
        print("\n" + "="*50)
        fix_infinity_focus()
    
    if args.interactive and not args.all:
        print("\n" + "="*50)
        interactive_focus()
    
    if args.verify or args.all:
        print("\n" + "="*50)
        verify_focus()
    
    print("\n" + "="*50)
    print("🎯 Focus diagnostic completed!")
    print("\n💡 Tips for aircraft detection:")
    print("   • Use lens position 0.0 (infinity focus)")
    print("   • Quality score should be > 100")
    print("   • Manual focus mode is recommended")
    print("   • Test in good lighting conditions")

if __name__ == "__main__":
    main()
