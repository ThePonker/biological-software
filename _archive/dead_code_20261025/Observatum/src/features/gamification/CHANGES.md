# Gamification Rare Species Update

## Summary
Wires up the Rare Species tab to use UKSI conservation status data.

## Files Changed

### calculator.py
**Added methods:**
- `_classify_rarity_tier(red_list, rarity, legal)` - Maps UKSI status fields to our 5 tiers
- `get_rare_species_observed()` - Queries observations against UKSI for rare species
- `get_rare_species_summary()` - Returns counts by tier
- `calculate_rare_milestones()` - Checks milestone rosette progress
- `get_rare_species_pins()` - Returns pin data for UI

**Tier Mapping:**
| Our Tier | UKSI Values |
|----------|-------------|
| Protected | `legal_protection` contains WACA Sch5/Sch8 or Habitats Regs |
| Critical | `red_list_status` starts with CR |
| Very Rare | `red_list_status` starts with EN |
| Rare | `red_list_status` starts with VU, or `rarity_status` = Nationally Rare/Notable A |
| Uncommon | `rarity_status` = Nationally Scarce/Notable/Notable B, or `red_list_status` = NT |

### window.py
**Updated imports:**
- Added `RARITY_TIERS`, `PAPER` from theme

**Replaced `_create_rare_tab()`:**
- Now shows summary bar with tier counts
- Filter buttons by rarity tier
- Milestone rosettes section
- Scrollable grid of species pins

**Added methods:**
- `_load_rare_species()` - Loads data into Rare Species tab
- `_create_milestone_card(milestone)` - Creates rosette milestone cards
- `_filter_rare_species(tier)` - Filters pins by tier
- `_render_rare_pins()` - Renders pin grid
- `_create_rare_pin_card(pin_data)` - Creates individual pin cards

**Updated `_load_data()`:**
- Now calls `self._load_rare_species()`

## How It Works
1. Queries `observations` table for unique `species_tvk` values
2. Joins against `uksi.taxa` to get conservation status columns
3. Classifies each species into a rarity tier (if any)
4. Displays pins coloured by tier with milestones

## Installation
1. Extract to `src/features/gamification/`
2. Restart Observatum
3. Open Achievements window → Rare Species tab
