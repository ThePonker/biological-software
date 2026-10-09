"""
Observatum V2 Gamification Calculator
======================================
Logic for calculating achievements from observation data.

Reads from:
- observatum.db (user observations)
- uksi.db (species taxonomy, family counts)

Writes to:
- gamification.db (achievement state)
"""

import sqlite3
import paths
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from .models import (
    UserProgress
)
from .theme import (
    get_tier_for_species_count, get_family_thresholds, get_taxonomic_group, get_vc_counts
)

# Import calculator modules
from .calc import RecordsCalculator, RareCalculator
from shared.db_open import connect_ro  # D9: reference data, read-only

# Try to import Paths from config
try:
    from src.core.config import Paths  # noqa: F401  (availability check / re-export)
    USE_CONFIG = True
except ImportError:
    USE_CONFIG = False


def _find_data_dir() -> Path:
    """Find the data directory when config is not available."""
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent.parent.parent
    return project_root / "data"


def get_db_path(name: str) -> Path:
    """Get path to a database file."""
    if USE_CONFIG:
        return paths.DATA_DIR / name
    else:
        return paths.DATA_DIR / name


class GamificationCalculator:
    """
    Calculates achievements based on observation data.
    
    Usage:
        calc = GamificationCalculator()
        new_achievements = calc.calculate_all()
        progress = calc.get_user_progress()
    """
    
    def __init__(self):
        self.observatum_db = str(paths.OBSERVATUM_DB)
        self.uksi_db = str(paths.UKSI_DB)
        self.gamification_db = str(paths.GAMIFICATION_DB)
        
        # Caches
        self._family_totals_cache: Dict[str, int] = {}
        
        # Initialize sub-calculators
        self._records_calc = RecordsCalculator(self._get_observatum_conn)
        self._rare_calc = RareCalculator(self._get_observatum_conn, self._get_uksi_conn)
    
    def _get_observatum_conn(self) -> sqlite3.Connection:
        """Get connection to observatum database."""
        return sqlite3.connect(str(self.observatum_db))
    
    def _get_uksi_conn(self) -> sqlite3.Connection:
        """Get connection to UKSI database."""
        return connect_ro(str(self.uksi_db))
    
    def _get_gamification_conn(self) -> sqlite3.Connection:
        """Get connection to gamification database."""
        return sqlite3.connect(str(self.gamification_db))
    
    # =========================================================================
    # BASIC STATS
    # =========================================================================
    
    def get_unique_species_count(self) -> int:
        """Get count of unique species observed."""
        conn = self._get_observatum_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(DISTINCT species_tvk) 
                FROM observations
                WHERE species_tvk IS NOT NULL AND species_tvk != ''
            """)
            result = cursor.fetchone()
            count = result[0] if result else 0
        except sqlite3.Error:
            count = 0
        finally:
            conn.close()
        
        return count
    
    def get_total_observations(self) -> int:
        """Get total observation count."""
        conn = self._get_observatum_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM observations")
            result = cursor.fetchone()
            count = result[0] if result else 0
        except sqlite3.Error:
            count = 0
        finally:
            conn.close()
        
        return count
    
    def get_observed_vcs(self) -> List[int]:
        """Get list of vice county numbers the user has observed in."""
        conn = self._get_observatum_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT DISTINCT vice_county_number 
                FROM observations
                WHERE vice_county_number IS NOT NULL
            """)
            vcs = [row[0] for row in cursor.fetchall() if row[0]]
        except sqlite3.Error:
            vcs = []
        finally:
            conn.close()
        
        return vcs
    
    def get_observed_families(self) -> Dict[str, Dict[str, Any]]:
        """Get dict of families observed with counts and dates."""
        conn = self._get_observatum_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    family,
                    order_name,
                    COUNT(DISTINCT species_tvk) as species_count,
                    MIN(date) as first_date
                FROM observations
                WHERE family IS NOT NULL AND family != ''
                    AND species_tvk IS NOT NULL
                GROUP BY family
                ORDER BY family
            """)
            
            families = {}
            for row in cursor.fetchall():
                family_name = row[0]
                families[family_name] = {
                    "order_name": row[1],
                    "count": row[2],
                    "first_date": row[3],
                }
        except sqlite3.Error:
            families = {}
        finally:
            conn.close()
        
        return families
    
    def get_family_total_species(self, family: str) -> int:
        """Get total species count for a family from UKSI."""
        if family in self._family_totals_cache:
            return self._family_totals_cache[family]
        
        conn = self._get_uksi_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM taxa
                WHERE family = ?
                    AND taxon_rank = 'Species'
            """, (family,))
            result = cursor.fetchone()
            total = result[0] if result else 0
        except sqlite3.Error:
            total = 0
        finally:
            conn.close()
        
        self._family_totals_cache[family] = total
        return total
    
    # =========================================================================
    # TIER CALCULATIONS
    # =========================================================================
    
    def calculate_current_tier(self) -> Dict[str, Any]:
        """Calculate the user's current tier based on unique species count."""
        species_count = self.get_unique_species_count()
        total_observations = self.get_total_observations()
        
        tier_info = get_tier_for_species_count(species_count)
        
        if tier_info["max_species"]:
            progress = (species_count - tier_info["min_species"]) / (tier_info["max_species"] - tier_info["min_species"])
            progress_percent = min(100, max(0, progress * 100))
            next_threshold = tier_info["max_species"]
        else:
            progress_percent = 100
            next_threshold = tier_info["min_species"]
        
        return {
            "tier_number": tier_info["tier"],
            "tier_name": tier_info["name"],
            "stage": tier_info["stage"],
            "unique_species": species_count,
            "total_observations": total_observations,
            "min_species": tier_info["min_species"],
            "max_species": tier_info["max_species"],
            "next_threshold": next_threshold,
            "progress_percent": progress_percent,
        }
    
    # =========================================================================
    # VICE COUNTY CALCULATIONS
    # =========================================================================
    
    def get_vice_county_coverage(self) -> Dict[str, Any]:
        """Get vice county coverage statistics."""
        observed_vcs = self.get_observed_vcs()
        all_vcs = get_vc_counts()
        
        regions = {
            "england": {"covered": 0, "total": 0},
            "wales": {"covered": 0, "total": 0},
            "scotland": {"covered": 0, "total": 0},
        }
        
        for vc_num, region in all_vcs.items():
            if region in regions:
                regions[region]["total"] += 1
                if vc_num in observed_vcs:
                    regions[region]["covered"] += 1
        
        return {
            "covered_vice_counties": len(observed_vcs),
            "total_vice_counties": len(all_vcs),
            "regions": regions,
        }
    
    def calculate_vice_county_badges(self) -> List[Dict[str, Any]]:
        """Calculate which VC badges have been earned."""
        observed_vcs = self.get_observed_vcs()
        all_vcs = get_vc_counts()
        
        badges = []
        for vc_num, region in all_vcs.items():
            badges.append({
                "vc_number": vc_num,
                "region": region,
                "earned": vc_num in observed_vcs,
            })
        
        badges.sort(key=lambda b: b["vc_number"])
        return badges
    
    def check_regional_trophies(self) -> List[Dict[str, Any]]:
        """Check for regional completion trophies."""
        coverage = self.get_vice_county_coverage()
        
        trophies = []
        for region, data in coverage["regions"].items():
            if data["covered"] == data["total"] and data["total"] > 0:
                trophies.append({
                    "region": region,
                    "type": "regional_completion",
                    "trophy_tier": "gold",
                })
        
        if len(trophies) == 3:
            trophies.append({
                "region": "uk",
                "type": "national_completion",
                "trophy_tier": "platinum",
            })
        
        return trophies
    
    # =========================================================================
    # FAMILY CALCULATIONS
    # =========================================================================
    
    def get_family_achievements(self) -> Dict[str, Any]:
        """Get family-based achievements (ribbons and medals)."""
        families = self.get_observed_families()
        
        ribbons = []
        medals = []
        
        for family_name, data in families.items():
            order_name = data["order_name"] or ""
            taxonomic_group = get_taxonomic_group(order_name)
            species_count = data["count"]
            
            # Family First ribbon
            ribbons.append({
                "family": family_name,
                "order": order_name,
                "group": taxonomic_group,
                "first_date": data["first_date"],
                "species_count": species_count,
            })
            
            # Family Depth medals
            family_total = self.get_family_total_species(family_name)
            if family_total > 0:
                thresholds = get_family_thresholds(family_total)
                
                for trophy_tier in ["bronze", "silver", "gold", "platinum"]:
                    if trophy_tier == "platinum":
                        threshold = family_total
                    elif trophy_tier == "gold":
                        threshold = int(family_total * thresholds["gold_pct"])
                    elif trophy_tier == "silver":
                        threshold = thresholds["silver"]
                    else:
                        threshold = thresholds["bronze"]
                    
                    if species_count >= threshold:
                        medals.append({
                            "family": family_name,
                            "order": order_name,
                            "group": taxonomic_group,
                            "trophy_tier": trophy_tier,
                            "species_count": species_count,
                            "family_total": family_total,
                            "threshold": threshold,
                        })
        
        return {
            "ribbons": ribbons,
            "medals": medals,
            "total_families": len(families),
        }
    
    # =========================================================================
    # USER PROGRESS & NOTIFICATIONS
    # =========================================================================
    
    def get_user_progress(self) -> UserProgress:
        """Get current user progress summary."""
        tier_data = self.calculate_current_tier()
        coverage = self.get_vice_county_coverage()
        family_data = self.get_family_achievements()
        
        return UserProgress(
            unique_species=tier_data["unique_species"],
            total_observations=tier_data["total_observations"],
            current_tier=tier_data["tier_number"],
            tier_name=tier_data["tier_name"],
            tier_progress=tier_data["progress_percent"],
            vice_counties_visited=coverage["covered_vice_counties"],
            families_recorded=family_data["total_families"],
        )
    
    def mark_notifications_read(self) -> int:
        """Mark all notifications as read. Returns count marked."""
        conn = self._get_gamification_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE notifications SET is_read = 1 WHERE is_read = 0
            """)
            count = cursor.rowcount
            conn.commit()
        except sqlite3.Error:
            count = 0
        finally:
            conn.close()
        
        return count
    
    def get_unread_notifications(self) -> List[Dict[str, Any]]:
        """Get list of unread notifications."""
        conn = self._get_gamification_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, achievement_type, achievement_name, message, created_at
                FROM notifications
                WHERE is_read = 0
                ORDER BY created_at DESC
            """)
            
            notifications = []
            for row in cursor.fetchall():
                notifications.append({
                    "id": row[0],
                    "type": row[1],
                    "name": row[2],
                    "message": row[3],
                    "created_at": row[4],
                })
        except sqlite3.Error:
            notifications = []
        finally:
            conn.close()
        
        return notifications
    
    # =========================================================================
    # RECORDS - Delegated to RecordsCalculator
    # =========================================================================
    
    def get_daily_species_counts(self, group: str = "general") -> Dict[str, int]:
        """Get species counts by date for a taxonomic group."""
        return self._records_calc.get_daily_counts(group)
    
    def get_annual_species_counts(self, group: str = "general") -> Dict[str, int]:
        """Get species counts by year for a taxonomic group."""
        return self._records_calc.get_annual_counts(group)
    
    def get_best_day(self, group: str = "general") -> Tuple[Optional[str], int]:
        """Get best single-day species count."""
        return self._records_calc.get_best_day(group)
    
    def get_best_year(self, group: str = "general") -> Tuple[Optional[str], int]:
        """Get best single-year species count."""
        return self._records_calc.get_best_year(group)
    
    def calculate_one_time_achievements(self) -> List[Dict[str, Any]]:
        """Calculate all one-time record achievements."""
        return self._records_calc.calculate_achievements()
    
    def get_one_time_achievements_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get achievements filtered by taxonomic group."""
        return self._records_calc.get_achievements_by_group(group)
    
    def get_one_time_achievements_summary(self) -> Dict[str, Any]:
        """Get summary of earned vs total achievements."""
        return self._records_calc.get_summary()
    
    # =========================================================================
    # RARE SPECIES - Delegated to RareCalculator
    # =========================================================================
    
    def get_rare_species_observed(self) -> List[Dict[str, Any]]:
        """Get all rare species the user has observed."""
        return self._rare_calc.get_observed()
    
    def get_rare_species_summary(self) -> Dict[str, Any]:
        """Get summary of rare species observations by tier."""
        return self._rare_calc.get_summary()
    
    def calculate_rare_milestones(self) -> List[Dict[str, Any]]:
        """Calculate milestone rosettes for rare species."""
        return self._rare_calc.calculate_milestones()
    
    def get_rare_species_pins(self) -> List[Dict[str, Any]]:
        """Get pin data for each rare species observed."""
        return self._rare_calc.get_pins()
    
    # =========================================================================
    # TOTAL ACHIEVEMENTS SUMMARY
    # =========================================================================
    
    def get_total_achievements_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of all achievement types."""
        tier_data = self.calculate_current_tier()
        vc_badges = self.calculate_vice_county_badges()
        family_data = self.get_family_achievements()
        rare_milestones = self.calculate_rare_milestones()
        records_summary = self._records_calc.get_summary()
        
        # Count achievements
        tier_earned = 1  # Current tier is earned
        tier_total = 20
        
        vcs_earned = sum(1 for b in vc_badges if b["earned"])
        vcs_total = len(vc_badges)
        
        ribbons_earned = family_data["total_families"]
        ribbons_total = ribbons_earned  # Dynamic
        
        medals_earned = len(family_data["medals"])
        medals_total = medals_earned  # Dynamic
        
        rare_earned = sum(1 for m in rare_milestones if m["earned"])
        rare_total = len(rare_milestones)
        
        records_earned = records_summary["earned"]
        records_total = records_summary["total"]
        
        # Calculate totals
        dynamic_earned = ribbons_earned + medals_earned
        static_earned = tier_earned + vcs_earned + rare_earned + records_earned
        static_total = tier_total + vcs_total + rare_total + records_total
        
        return {
            "total_earned": static_earned + dynamic_earned,
            "total_possible": static_total + dynamic_earned,
            "breakdown": {
                "tiers": {"earned": tier_earned, "total": tier_total},
                "vcs": {"earned": vcs_earned, "total": vcs_total},
                "ribbons": {"earned": ribbons_earned, "total": ribbons_earned},
                "medals": {"earned": medals_earned, "total": medals_earned},
                "rare": {"earned": rare_earned, "total": rare_total},
                "records": {"earned": records_earned, "total": records_total},
            }
        }
