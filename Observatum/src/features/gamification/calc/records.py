"""
Records Calculator Module.

Handles daily and annual species count records by taxonomic group.
Reduces code duplication through parameterized queries.
"""

import sqlite3
from typing import Dict, List, Any, Optional, Tuple

from ..theme import (
    ONE_TIME_ACHIEVEMENTS, SEAL_COLOURS,
    ACHIEVEMENT_GROUP_ORDERS, BUTTERFLY_FAMILIES, 
    HOVERFLY_FAMILIES, ACULEATE_FAMILIES,
    get_seal_colour
)


# Group filter definitions for cleaner query building
GROUP_FILTERS = {
    "general": {
        "type": "none",  # No filter
    },
    "birds": {
        "type": "order",
        "orders": ACHIEVEMENT_GROUP_ORDERS.get("birds", []),
    },
    "butterflies": {
        "type": "family",
        "families": BUTTERFLY_FAMILIES,
    },
    "moths": {
        "type": "exclude_family",
        "order": "Lepidoptera",
        "exclude_families": BUTTERFLY_FAMILIES,
    },
    "dragonflies": {
        "type": "order",
        "orders": ["Odonata"],
    },
    "plants": {
        "type": "kingdom",
        "kingdom": "Plantae",
    },
    "hoverflies": {
        "type": "family",
        "families": HOVERFLY_FAMILIES,
    },
    "beetles": {
        "type": "order",
        "orders": ["Coleoptera"],
    },
    "aculeates": {
        "type": "family",
        "families": ACULEATE_FAMILIES,
    },
    "spiders": {
        "type": "order",
        "orders": ["Araneae"],
    },
    "fungi": {
        "type": "kingdom",
        "kingdom": "Fungi",
    },
}


class RecordsCalculator:
    """
    Calculates daily and annual species records.
    
    Provides cleaner API for record queries with less code duplication.
    """
    
    def __init__(self, get_conn_func):
        """
        Initialize with database connection function.
        
        Args:
            get_conn_func: Function that returns sqlite3 Connection to observatum.db
        """
        self._get_conn = get_conn_func
    
    def _build_group_query(self, base_query: str, group: str, time_field: str) -> Tuple[str, list]:
        """
        Build a query with appropriate WHERE clause for the taxonomic group.
        
        Args:
            base_query: Base SELECT query
            group: Taxonomic group name
            time_field: Either 'date' for daily or time extraction for annual
        
        Returns:
            (query_string, params_list)
        """
        filter_def = GROUP_FILTERS.get(group)
        if not filter_def:
            return "", []
        
        base_where = """
            WHERE species_tvk IS NOT NULL AND species_tvk != ''
            AND date IS NOT NULL
        """
        
        filter_type = filter_def["type"]
        
        if filter_type == "none":
            query = f"""
                SELECT {time_field}, COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                {base_where}
                GROUP BY {time_field}
            """
            return query, []
        
        elif filter_type == "order":
            orders = filter_def["orders"]
            placeholders = ",".join("?" * len(orders))
            query = f"""
                SELECT {time_field}, COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                {base_where}
                AND order_name IN ({placeholders})
                GROUP BY {time_field}
            """
            return query, list(orders)
        
        elif filter_type == "family":
            families = filter_def["families"]
            placeholders = ",".join("?" * len(families))
            query = f"""
                SELECT {time_field}, COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                {base_where}
                AND family IN ({placeholders})
                GROUP BY {time_field}
            """
            return query, list(families)
        
        elif filter_type == "exclude_family":
            order = filter_def["order"]
            exclude = filter_def["exclude_families"]
            placeholders = ",".join("?" * len(exclude))
            query = f"""
                SELECT {time_field}, COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                {base_where}
                AND order_name = ?
                AND family NOT IN ({placeholders})
                GROUP BY {time_field}
            """
            return query, [order] + list(exclude)
        
        elif filter_type == "kingdom":
            kingdom = filter_def["kingdom"]
            query = f"""
                SELECT {time_field}, COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                {base_where}
                AND kingdom = ?
                GROUP BY {time_field}
            """
            return query, [kingdom]
        
        return "", []
    
    def get_daily_counts(self, group: str = "general") -> Dict[str, int]:
        """
        Get species counts by date for a taxonomic group.
        
        Args:
            group: Taxonomic group (general, birds, butterflies, etc.)
        
        Returns:
            Dict mapping date strings to species counts
        """
        query, params = self._build_group_query("", group, "date")
        if not query:
            return {}
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            results = {row[0]: row[1] for row in cursor.fetchall()}
        except sqlite3.Error:
            results = {}
        finally:
            conn.close()
        
        return results
    
    def get_annual_counts(self, group: str = "general") -> Dict[str, int]:
        """
        Get unique species counts by year for a taxonomic group.
        
        Args:
            group: Taxonomic group (general, birds, butterflies, etc.)
        
        Returns:
            Dict mapping year strings to unique species counts
        """
        filter_def = GROUP_FILTERS.get(group)
        if not filter_def:
            return {}
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # For annual counts, we need DISTINCT species per year
            base_where = """
                WHERE species_tvk IS NOT NULL AND species_tvk != ''
                AND date IS NOT NULL
            """
            
            filter_type = filter_def["type"]
            
            if filter_type == "none":
                cursor.execute(f"""
                    SELECT substr(date, 1, 4) as year, COUNT(DISTINCT species_tvk)
                    FROM observations
                    {base_where}
                    GROUP BY substr(date, 1, 4)
                """)
            elif filter_type == "order":
                orders = filter_def["orders"]
                placeholders = ",".join("?" * len(orders))
                cursor.execute(f"""
                    SELECT substr(date, 1, 4) as year, COUNT(DISTINCT species_tvk)
                    FROM observations
                    {base_where}
                    AND order_name IN ({placeholders})
                    GROUP BY substr(date, 1, 4)
                """, orders)
            elif filter_type == "family":
                families = filter_def["families"]
                placeholders = ",".join("?" * len(families))
                cursor.execute(f"""
                    SELECT substr(date, 1, 4) as year, COUNT(DISTINCT species_tvk)
                    FROM observations
                    {base_where}
                    AND family IN ({placeholders})
                    GROUP BY substr(date, 1, 4)
                """, families)
            elif filter_type == "exclude_family":
                order = filter_def["order"]
                exclude = filter_def["exclude_families"]
                placeholders = ",".join("?" * len(exclude))
                cursor.execute(f"""
                    SELECT substr(date, 1, 4) as year, COUNT(DISTINCT species_tvk)
                    FROM observations
                    {base_where}
                    AND order_name = ?
                    AND family NOT IN ({placeholders})
                    GROUP BY substr(date, 1, 4)
                """, [order] + list(exclude))
            elif filter_type == "kingdom":
                kingdom = filter_def["kingdom"]
                cursor.execute(f"""
                    SELECT substr(date, 1, 4) as year, COUNT(DISTINCT species_tvk)
                    FROM observations
                    {base_where}
                    AND kingdom = ?
                    GROUP BY substr(date, 1, 4)
                """, [kingdom])
            else:
                return {}
            
            results = {row[0]: row[1] for row in cursor.fetchall()}
        except sqlite3.Error:
            results = {}
        finally:
            conn.close()
        
        return results
    
    def get_best_day(self, group: str = "general") -> Tuple[Optional[str], int]:
        """Get the best single-day species count for a group."""
        counts = self.get_daily_counts(group)
        if not counts:
            return None, 0
        best_date = max(counts.keys(), key=lambda d: counts[d])
        return best_date, counts[best_date]
    
    def get_best_year(self, group: str = "general") -> Tuple[Optional[str], int]:
        """Get the best single-year species count for a group."""
        counts = self.get_annual_counts(group)
        if not counts:
            return None, 0
        best_year = max(counts.keys(), key=lambda y: counts[y])
        return best_year, counts[best_year]
    
    def calculate_achievements(self) -> List[Dict[str, Any]]:
        """
        Calculate all one-time record achievements.
        
        Returns list of achievement dicts with earned status.
        """
        achievements = []
        
        for achievement in ONE_TIME_ACHIEVEMENTS:
            group = achievement["group"]
            period = achievement["period"]
            threshold = achievement["threshold"]
            
            # Get best count for this period/group
            if period == "daily":
                best_date, best_count = self.get_best_day(group)
            else:
                best_date, best_count = self.get_best_year(group)
            
            earned = best_count >= threshold
            colour = get_seal_colour(group)
            
            achievements.append({
                "name": achievement["name"],
                "group": group,
                "period": period,
                "threshold": threshold,
                "best_count": best_count,
                "best_date": best_date,
                "best_value": best_count,
                "earned": earned,
                "colour": colour,
            })
        
        return achievements
    
    def get_achievements_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get achievements filtered by taxonomic group."""
        all_achievements = self.calculate_achievements()
        return [a for a in all_achievements if a["group"] == group]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of earned vs total achievements."""
        achievements = self.calculate_achievements()
        earned = sum(1 for a in achievements if a["earned"])
        return {
            "earned": earned,
            "total": len(achievements),
            "percent": int((earned / len(achievements)) * 100) if achievements else 0,
        }
