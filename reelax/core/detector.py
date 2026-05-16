"""Ad and keyword detection module for reelax.

Uses a multi-strategy approach:
1. UIAutomator2 (fastest, most reliable)
2. ADB dumpsys (slower fallback if uia2 is unavailable)
"""

import subprocess
from typing import List

from loguru import logger

from reelax.core.adb import ADBDevice


AD_MARKERS = [
    "Sponsored",
    "paid partnership",     # Creator ads
    "paid partnership with",
    "Ad",
    "Shop Now",
    "Learn More",
    "Install Now"
]


def is_ad_reel(device: ADBDevice) -> bool:
    """
    Check if current reel is an ad.
    Uses UIAutomator2 if available, falls back to dumpsys.
    """
    u2_dev = device.get_u2()
    
    # Strategy 1: UIAutomator2 — scan visible text for ad markers
    if u2_dev:
        try:
            for marker in AD_MARKERS:
                if u2_dev(textContains=marker).exists(timeout=0.5):
                    logger.debug(f"Ad detected via UIAutomator2 text: '{marker}'")
                    return True
                if u2_dev(descriptionContains=marker).exists(timeout=0.3):
                    logger.debug(f"Ad detected via UIAutomator2 content-desc: '{marker}'")
                    return True
        except Exception as e:
            logger.warning(f"UIAutomator2 ad scan failed: {e}, falling back to dumpsys")
    
    # Strategy 2: Fallback — dumpsys activity
    return _dumpsys_ad_check(device)


import re

def _dumpsys_ad_check(device: ADBDevice) -> bool:
    """Scan dumpsys for Sponsored keyword — last resort."""
    try:
        # Build regex from markers for python re module
        pattern = re.compile("|".join(re.escape(m) for m in AD_MARKERS), re.IGNORECASE)
        result = subprocess.run(
            ["adb", "-s", device.serial, "shell", "dumpsys", "activity", "top"],
            capture_output=True, text=True, timeout=3, shell=False
        )
        return bool(pattern.search(result.stdout))
    except Exception:
        return False


def is_blocked_keyword(device: ADBDevice, blocklist: List[str]) -> bool:
    """
    Check if current reel contains any user-blocked keyword.
    Uses UIAutomator2 to dump visible text on screen, falls back to dumpsys.
    """
    if not blocklist:
        return False
        
    u2_dev = device.get_u2()
    
    if u2_dev:
        try:
            # Get all text content on screen
            xml_dump = u2_dev.dump_hierarchy()
            xml_lower = xml_dump.lower()
            for keyword in blocklist:
                if keyword.lower() in xml_lower:
                    logger.debug(f"Blocked keyword detected via UIAutomator2: '{keyword}'")
                    return True
            return False
        except Exception as e:
            logger.warning(f"Keyword check via UIAutomator2 failed: {e}")
            
    # Fallback to dumpsys
    try:
        pattern = re.compile("|".join(re.escape(k) for k in blocklist), re.IGNORECASE)
        result = subprocess.run(
            ["adb", "-s", device.serial, "shell", "dumpsys", "activity", "top"],
            capture_output=True, text=True, timeout=3, shell=False
        )
        return bool(pattern.search(result.stdout))
    except Exception:
        return False
