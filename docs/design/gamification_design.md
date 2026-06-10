# Observatum V2 Gamification System Design

## 1. Overview

The gamification system for Observatum V2 is a modular, optional feature designed to encourage ecological exploration and recording across all UK taxonomic groups. It consists of three core components: **Tiers**, **Badges**, and **Trophies**.

The system can be toggled on/off via settings. When disabled, all data continues to be tracked in the background but UI elements are hidden.

---

## 2. System Architecture

### Data Strategy
- **Tiers & Trophies**: Stored in dedicated database tables with timestamps and context
- **Badges**: Calculated dynamically from observation data (no storage required)
- **Vice County Map**: Visual representation derived from observation location data

### Core Tables
```
gamification_tiers (tier progression history)
├── tier_number: INT (1-20)
├── date_reached: DATETIME
├── species_count: INT (unique species recorded)
└── observation_count: INT (total observations)

gamification_trophies (earned trophies)
├── trophy_type: STRING (observation_milestone | family_completion | regional_completion)
├── trophy_name: STRING (human-readable name)
├── date_earned: DATETIME
└── context_data: JSON (additional context)
```

---

## 3. Observation Tiers

**System:** 20 tiers tracking unique species recorded

**Progression:** Linear, 500 unique species per tier

| Tier | Species Range | Tier Name |
|------|---------------|-----------|
| 1    | 0-500         | Junior Naturalist |
| 2    | 500-1,000     | Naturalist Third Class |
| 3    | 1,000-1,500   | Naturalist Second Class |
| 4    | 1,500-2,000   | Naturalist First Class |
| 5    | 2,000-2,500   | Senior Naturalist |
| 6    | 2,500-3,000   | Principal Naturalist |
| 7    | 3,000-3,500   | Deputy Director of Field Studies |
| 8    | 3,500-4,000   | Director of Biological Collections |
| 9    | 4,000-4,500   | Chief Naturalist |
| 10   | 4,500-5,000   | Grand Naturalist |
| 11   | 5,000-5,500   | Rector of Natural Investigation |
| 12   | 5,500-6,000   | Chancellor of Ecological Sciences |
| 13   | 6,000-6,500   | Provost of Faunal Studies |
| 14   | 6,500-7,000   | Archon of Naturalism |
| 15   | 7,000-7,500   | Supreme Naturalist |
| 16   | 7,500-8,000   | Grand Chancellor of Natural Philosophy |
| 17   | 8,000-8,500   | Keeper of the Naturalist's Seat |
| 18   | 8,500-9,000   | Patriarch of Field Investigation |
| 19   | 9,000-9,500   | Imperator of Natural Sciences |
| 20   | 9,500-10,000  | Eternal Guardian of Living Knowledge |

**Data Tracked:**
- Date tier reached
- Species count at reach
- Observation count at reach

---

## 4. Badge System

Badges are repeatable achievements and are calculated dynamically from observation data.

### 4.1 Observation Count Badges (40 total)

**Threshold:** Every 2,500 observations

```
2,500, 5,000, 7,500, 10,000, 12,500, 15,000, 17,500, 20,000, 22,500, 25,000,
27,500, 30,000, 32,500, 35,000, 37,500, 40,000, 42,500, 45,000, 47,500, 50,000,
52,500, 55,000, 57,500, 60,000, 62,500, 65,000, 67,500, 70,000, 72,500, 75,000,
77,500, 80,000, 82,500, 85,000, 87,500, 90,000, 92,500, 95,000, 97,500, 100,000
```

**Calculation:** `unique_observations >= threshold`

---

### 4.2 Species Diversity Per Group Badges (28 per group)

**Scope:** Applied to all taxonomic levels (Class, Order, Family)

**Thresholds:**
- 0-90%: Every 5% (18 badges)
  - 5%, 10%, 15%, 20%, 25%, 30%, 35%, 40%, 45%, 50%, 55%, 60%, 65%, 70%, 75%, 80%, 85%, 90%
- 90-100%: Every 1% (10 badges)
  - 91%, 92%, 93%, 94%, 95%, 96%, 97%, 98%, 99%, 100%

**Calculation per group:**
```
percentage = (species_recorded_in_group / total_species_in_group) * 100
badge_earned = percentage >= threshold_percentage
```

**Example - Coleoptera (6,939 species):**
- 5% badge = 347 species recorded
- 10% badge = 694 species recorded
- 50% badge = 3,470 species recorded
- 100% badge = 6,939 species recorded

**Number of badges:** 28 × (number of groups user has recorded in)
- Max potential: 28 × 333 classes + 28 × 1,222 orders + 28 × 13,000+ families

---

### 4.3 Vice County Coverage Badges (112 total)

**One badge per UK vice county**

**Threshold:** At least one observation recorded in that vice county

**Calculation:**
```
badge_earned = observations.filter(vice_county == target_vice_county).count() >= 1
```

**Display:** Vice county map shows progress (counties turn green when first observation recorded)

---

## 5. Trophy System

Trophies are one-time, special achievements. They are stored in the database with context.

### 5.1 Observation Milestones (10 trophies)

**Thresholds:** Every 10,000 observations

```
10,000, 20,000, 30,000, 40,000, 50,000, 60,000, 70,000, 80,000, 90,000, 100,000
```

**Data Stored:**
- Trophy name (e.g., "10,000 Observations")
- Date earned
- Observation count at earned
- Species count at earned

---

### 5.2 Family Completion Trophies (Dynamic)

**Mechanism:** Dynamic trophy generation as user records in families

1. User records first species from Family X → Family X becomes "tracked"
2. Trophy appears with progress indicator (e.g., "15% of Carabidae")
3. User records species in Family X until 100% complete
4. Trophy earned and locked

**Data Stored:**
- Trophy name (e.g., "Carabidae Complete")
- Family TVK identifier
- Date earned
- Total species in family
- Final species count recorded from family

**Calculation:**
```
percentage = (species_recorded_in_family / total_species_in_family) * 100
trophy_earned = percentage == 100%
```

---

### 5.3 Regional Completion Trophies (4 trophies)

**Mechanism:** Track vice county coverage by region

**Regions:**
1. **England Complete**
   - Require: Observations in all English vice counties
   - Data stored: Date completed, final observation count, final species count

2. **Scotland Complete**
   - Require: Observations in all Scottish vice counties
   - Data stored: Date completed, final observation count, final species count

3. **Wales Complete**
   - Require: Observations in all Welsh vice counties
   - Data stored: Date completed, final observation count, final species count

4. **UK Complete**
   - Require: Observations in all 112 UK vice counties
   - Data stored: Date completed, final observation count, final species count

**Calculation:**
```
english_vice_counties_with_observations = observations.filter(region == 'England').distinct(vice_county).count()
total_english_vice_counties = 65  (example)
england_complete = english_vice_counties_with_observations == total_english_vice_counties
```

---

## 6. Data Model Summary

### Tiers
```json
{
  "tier_id": "integer",
  "tier_number": "integer (1-20)",
  "date_reached": "datetime",
  "species_count": "integer",
  "observation_count": "integer"
}
```

### Trophies
```json
{
  "trophy_id": "integer",
  "trophy_type": "string (observation_milestone | family_completion | regional_completion)",
  "trophy_name": "string",
  "date_earned": "datetime",
  "context_data": {
    "species_count_at_earned": "integer",
    "observation_count_at_earned": "integer",
    "family_tvk": "string (optional, for family_completion)",
    "region": "string (optional, for regional_completion)"
  }
}
```

---

## 7. Calculation Logic

### When Calculations Occur

**On-demand (when gamification UI is opened):**
- Observation count badges
- Species diversity badges
- Vice county badges
- Current tier

**On observation save:**
- Check if tier milestone reached → store if true
- Check if family completion achieved → store if true
- Check if regional completion achieved → store if true

### Pseudo-code Example: Badge Calculation

```python
def get_earned_badges(user_id):
    observations = get_user_observations(user_id)
    
    # Observation count badges
    total_obs = observations.count()
    obs_badges = [2500, 5000, 7500, ...]
    earned = [badge for badge in obs_badges if total_obs >= badge]
    
    # Species diversity badges per group
    for group in get_recorded_groups(user_id):
        species_in_group = observations.distinct(species).filter(group=group).count()
        total_species_in_group = get_total_species_in_group(group)
        percentage = (species_in_group / total_species_in_group) * 100
        
        thresholds = [5, 10, 15, ..., 100]
        earned_in_group = [t for t in thresholds if percentage >= t]
    
    # Vice county badges
    vice_counties_with_obs = observations.distinct(vice_county)
    earned.extend(vice_counties_with_obs)
    
    return earned
```

---

## 8. Gamification Toggle

**Feature:** Can be enabled/disabled in settings

**Behavior:**
- **When enabled:** Full gamification UI displayed (tiers, badges, trophies, vice county map)
- **When disabled:** All UI elements hidden, but data continues to be tracked in background
- **Data persistence:** Tiers and trophies remain stored; badges recalculate when re-enabled

**Implementation:** Modular bolt-on feature, separate from core observation recording

---

## 9. UI Components (To Be Designed)

- **Tier display** (current tier, progress to next tier, tier history)
- **Badge collection** (filtered by type, progress indicators for in-progress badges)
- **Trophy showcase** (earned trophies, progress on family completions, regional challenges)
- **Vice county map** (interactive map showing covered counties, progress percentage)
- **Progress dashboard** (overview of all gamification progress)

---

## 10. Notes & Future Considerations

- Tier names/themes should be defined alongside UI design
- Vice county data requires location tracking in observations
- Family completion trophies create unbounded trophy count (scales with user's recording breadth)
- All calculations are deterministic and can be recalculated at any time from raw observation data
- System is designed to scale to 100,000+ observations

