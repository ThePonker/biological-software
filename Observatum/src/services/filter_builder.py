"""
Filter Builder Service.

Combines filter configurations from all dialogs and generates SQL.
Handles complex AND/OR/NOT logic for multi-select filters.
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class FilterClause:
    """Represents a single filter clause."""
    column: str
    operator: str  # 'IN', 'NOT IN', 'LIKE', 'NOT LIKE', '=', '!=', '>=', '<=', 'BETWEEN'
    values: List[Any]
    mode: str = 'include'  # 'include' or 'exclude'
    
    def to_sql(self) -> str:
        """Convert to SQL string."""
        if not self.values:
            return ""
        
        if self.operator in ('IN', 'NOT IN'):
            escaped = [str(v).replace("'", "''") for v in self.values]
            values_str = ", ".join(f"'{v}'" for v in escaped)
            return f"{self.column} {self.operator} ({values_str})"
        
        elif self.operator in ('LIKE', 'NOT LIKE'):
            escaped = str(self.values[0]).replace("'", "''")
            return f"{self.column} {self.operator} '{escaped}'"
        
        elif self.operator == 'BETWEEN':
            v1 = str(self.values[0]).replace("'", "''")
            v2 = str(self.values[1]).replace("'", "''")
            return f"{self.column} BETWEEN '{v1}' AND '{v2}'"
        
        elif self.operator in ('=', '!=', '>=', '<=', '>', '<'):
            escaped = str(self.values[0]).replace("'", "''")
            return f"{self.column} {self.operator} '{escaped}'"
        
        return ""
    
    def to_parameterized(self) -> Tuple[str, Tuple]:
        """Convert to parameterized SQL (clause, params)."""
        if not self.values:
            return ("", ())
        
        if self.operator in ('IN', 'NOT IN'):
            placeholders = ", ".join("?" for _ in self.values)
            clause = f"{self.column} {self.operator} ({placeholders})"
            return (clause, tuple(self.values))
        
        elif self.operator in ('LIKE', 'NOT LIKE'):
            return (f"{self.column} {self.operator} ?", (self.values[0],))
        
        elif self.operator == 'BETWEEN':
            return (f"{self.column} BETWEEN ? AND ?", (self.values[0], self.values[1]))
        
        elif self.operator in ('=', '!=', '>=', '<=', '>', '<'):
            return (f"{self.column} {self.operator} ?", (self.values[0],))
        
        return ("", ())


@dataclass
class FilterConfig:
    """Complete filter configuration from wizard."""
    # What filters
    species: Optional[Dict] = None       # {'value': str, 'mode': str}
    order: Optional[Dict] = None         # {'selected': List, 'mode': str}
    family: Optional[Dict] = None        # {'selected': List, 'mode': str}
    
    # Where filters  
    vice_county: Optional[Dict] = None   # {'selected': List, 'mode': str}
    grid_ref: Optional[Dict] = None      # {'value': str, 'mode': str}
    site_name: Optional[Dict] = None     # {'value': str, 'mode': str}
    
    # When filters
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    
    # Who filters
    recorder: Optional[Dict] = None      # {'value': str, 'mode': str}
    determiner: Optional[Dict] = None    # {'value': str, 'mode': str}
    
    # How filters
    method: Optional[Dict] = None        # {'selected': List, 'mode': str}
    
    # Status filters
    verification_status: Optional[Dict] = None  # {'selected': List, 'mode': str}
    record_type: Optional[Dict] = None   # {'selected': List, 'mode': str}


class FilterBuilder:
    """
    Builds SQL WHERE clauses from filter configurations.
    
    Usage:
        builder = FilterBuilder()
        builder.set_config(filter_config)
        
        # Get SQL string
        where_clause = builder.build_where_clause()
        
        # Get parameterized query
        clause, params = builder.build_parameterized()
    """
    
    # Column mappings for different tables
    COLUMN_MAP = {
        'observations': {
            'species': 'species_name',
            'order': 'order_name',
            'family': 'family',
            'vice_county': 'vc_number',
            'grid_ref': 'grid_ref',
            'site_name': 'site_name',
            'date': 'date',
            'recorder': 'recorder',
            'determiner': 'determiner',
            'method': 'sample_method',
            'verification_status': 'verification_status',
            'record_type': 'record_type',
        },
        'recording_scheme': {
            'species': 'species_name',
            'order': 'order_name',
            'family': 'family',
            'vice_county': 'vc_number',
            'grid_ref': 'grid_ref',
            'site_name': 'site_name',
            'date': 'date',
            'recorder': 'recorder',
            'determiner': 'determiner',
            'method': 'sample_method',
            'verification_status': 'verification_status',
        },
        'specimens': {
            'species': 'species_name',
            'order': 'order_name',
            'family': 'family',
            'vice_county': 'vc_number',
            'grid_ref': 'grid_ref',
            'site_name': 'locality',
            'date': 'collection_date',
            'collector': 'collector',
        }
    }
    
    def __init__(self, table: str = 'observations'):
        self._table = table
        self._config: Optional[FilterConfig] = None
        self._clauses: List[FilterClause] = []
    
    def set_table(self, table: str):
        """Set the target table for column mapping."""
        self._table = table
    
    def set_config(self, config: FilterConfig):
        """Set the filter configuration."""
        self._config = config
        self._build_clauses()
    
    def set_config_dict(self, config_dict: Dict[str, Any]):
        """Set configuration from a dictionary."""
        self._config = FilterConfig(**config_dict)
        self._build_clauses()
    
    def _get_column(self, filter_key: str) -> str:
        """Get the actual column name for a filter key."""
        table_map = self.COLUMN_MAP.get(self._table, self.COLUMN_MAP['observations'])
        return table_map.get(filter_key, filter_key)
    
    def _build_clauses(self):
        """Build filter clauses from config."""
        self._clauses = []
        
        if not self._config:
            return
        
        # Species filter
        if self._config.species:
            col = self._get_column('species')
            value = self._config.species.get('value', '')
            mode = self._config.species.get('mode', 'include')
            if value:
                op = 'LIKE' if mode == 'include' else 'NOT LIKE'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=[f'%{value}%'],
                    mode=mode
                ))
        
        # Order filter (multi-select)
        if self._config.order:
            col = self._get_column('order')
            selected = self._config.order.get('selected', [])
            mode = self._config.order.get('mode', 'include')
            if selected:
                op = 'IN' if mode == 'include' else 'NOT IN'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=selected,
                    mode=mode
                ))
        
        # Family filter (multi-select)
        if self._config.family:
            col = self._get_column('family')
            selected = self._config.family.get('selected', [])
            mode = self._config.family.get('mode', 'include')
            if selected:
                op = 'IN' if mode == 'include' else 'NOT IN'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=selected,
                    mode=mode
                ))
        
        # Vice County filter (multi-select)
        if self._config.vice_county:
            col = self._get_column('vice_county')
            selected = self._config.vice_county.get('selected', [])
            mode = self._config.vice_county.get('mode', 'include')
            if selected:
                # Extract VC numbers from formatted strings like "24 - Bucks"
                vc_numbers = []
                for vc in selected:
                    if isinstance(vc, str) and ' - ' in vc:
                        try:
                            vc_numbers.append(int(vc.split(' - ')[0]))
                        except ValueError:
                            vc_numbers.append(vc)
                    else:
                        vc_numbers.append(vc)
                
                op = 'IN' if mode == 'include' else 'NOT IN'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=vc_numbers,
                    mode=mode
                ))
        
        # Grid Reference filter
        if self._config.grid_ref:
            col = self._get_column('grid_ref')
            value = self._config.grid_ref.get('value', '')
            mode = self._config.grid_ref.get('mode', 'include')
            if value:
                op = 'LIKE' if mode == 'include' else 'NOT LIKE'
                self._clauses.append(FilterClause(
                    column=f"UPPER({col})",
                    operator=op,
                    values=[f'{value.upper()}%'],
                    mode=mode
                ))
        
        # Site Name filter
        if self._config.site_name:
            col = self._get_column('site_name')
            value = self._config.site_name.get('value', '')
            mode = self._config.site_name.get('mode', 'include')
            if value:
                op = 'LIKE' if mode == 'include' else 'NOT LIKE'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=[f'%{value}%'],
                    mode=mode
                ))
        
        # Date range filters
        date_col = self._get_column('date')
        if self._config.date_from and self._config.date_to:
            self._clauses.append(FilterClause(
                column=date_col,
                operator='BETWEEN',
                values=[self._config.date_from, self._config.date_to]
            ))
        elif self._config.date_from:
            self._clauses.append(FilterClause(
                column=date_col,
                operator='>=',
                values=[self._config.date_from]
            ))
        elif self._config.date_to:
            self._clauses.append(FilterClause(
                column=date_col,
                operator='<=',
                values=[self._config.date_to]
            ))
        
        # Year filter
        if self._config.year:
            self._clauses.append(FilterClause(
                column=f"strftime('%Y', {date_col})",
                operator='=',
                values=[str(self._config.year)]
            ))
        
        # Month filter
        if self._config.month:
            self._clauses.append(FilterClause(
                column=f"strftime('%m', {date_col})",
                operator='=',
                values=[f'{self._config.month:02d}']
            ))
        
        # Recorder filter
        if self._config.recorder:
            col = self._get_column('recorder')
            value = self._config.recorder.get('value', '')
            mode = self._config.recorder.get('mode', 'include')
            if value:
                op = 'LIKE' if mode == 'include' else 'NOT LIKE'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=[f'%{value}%'],
                    mode=mode
                ))
        
        # Determiner filter
        if self._config.determiner:
            col = self._get_column('determiner')
            value = self._config.determiner.get('value', '')
            mode = self._config.determiner.get('mode', 'include')
            if value:
                op = 'LIKE' if mode == 'include' else 'NOT LIKE'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=[f'%{value}%'],
                    mode=mode
                ))
        
        # Method filter (multi-select)
        if self._config.method:
            col = self._get_column('method')
            selected = self._config.method.get('selected', [])
            mode = self._config.method.get('mode', 'include')
            if selected:
                op = 'IN' if mode == 'include' else 'NOT IN'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=selected,
                    mode=mode
                ))
        
        # Verification Status filter (multi-select)
        if self._config.verification_status:
            col = self._get_column('verification_status')
            selected = self._config.verification_status.get('selected', [])
            mode = self._config.verification_status.get('mode', 'include')
            if selected:
                op = 'IN' if mode == 'include' else 'NOT IN'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=selected,
                    mode=mode
                ))
        
        # Record Type filter (multi-select)
        if self._config.record_type:
            col = self._get_column('record_type')
            selected = self._config.record_type.get('selected', [])
            mode = self._config.record_type.get('mode', 'include')
            if selected:
                op = 'IN' if mode == 'include' else 'NOT IN'
                self._clauses.append(FilterClause(
                    column=col,
                    operator=op,
                    values=selected,
                    mode=mode
                ))
    
    def build_where_clause(self) -> str:
        """
        Build complete WHERE clause (without 'WHERE' keyword).
        
        Returns:
            SQL clause string, e.g., "order_name IN ('Coleoptera') AND vc_number = 24"
        """
        if not self._clauses:
            return ""
        
        sql_parts = []
        for clause in self._clauses:
            sql = clause.to_sql()
            if sql:
                sql_parts.append(sql)
        
        return " AND ".join(sql_parts)
    
    def build_parameterized(self) -> Tuple[str, Tuple]:
        """
        Build parameterized WHERE clause.
        
        Returns:
            (clause_string, params_tuple)
        """
        if not self._clauses:
            return ("", ())
        
        clause_parts = []
        all_params = []
        
        for clause in self._clauses:
            sql, params = clause.to_parameterized()
            if sql:
                clause_parts.append(sql)
                all_params.extend(params)
        
        return (" AND ".join(clause_parts), tuple(all_params))
    
    def has_filters(self) -> bool:
        """Return True if any filters are active."""
        return len(self._clauses) > 0
    
    def get_active_filter_count(self) -> int:
        """Return number of active filter clauses."""
        return len(self._clauses)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of active filters."""
        if not self._clauses:
            return "No filters active"
        
        summaries = []
        for clause in self._clauses:
            if clause.operator in ('IN', 'NOT IN'):
                count = len(clause.values)
                mode = "including" if clause.operator == 'IN' else "excluding"
                summaries.append(f"{clause.column}: {mode} {count} values")
            else:
                summaries.append(f"{clause.column} {clause.operator} {clause.values[0]}")
        
        return "; ".join(summaries)


# Convenience function
def build_filter_sql(config: Dict[str, Any], table: str = 'observations') -> str:
    """
    Quick function to build SQL from a config dict.
    
    Args:
        config: Filter configuration dictionary
        table: Target table name
        
    Returns:
        SQL WHERE clause string
    """
    builder = FilterBuilder(table)
    builder.set_config_dict(config)
    return builder.build_where_clause()
