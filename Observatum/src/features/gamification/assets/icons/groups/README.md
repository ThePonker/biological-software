# Group Icons for Record Seals

Place SVG silhouette icons here to customise the centre of achievement seals.

## Expected Files

| Filename | Group | Description |
|----------|-------|-------------|
| `birds.svg` | Birds | Bird silhouette |
| `butterflies.svg` | Butterflies | Butterfly silhouette |
| `moths.svg` | Moths | Moth silhouette |
| `dragonflies.svg` | Dragonflies | Dragonfly silhouette |
| `plants.svg` | Plants | Leaf or flower silhouette |
| `hoverflies.svg` | Hoverflies | Hoverfly silhouette |
| `beetles.svg` | Beetles | Beetle silhouette |
| `aculeates.svg` | Bees/Wasps/Ants | Bee silhouette |
| `spiders.svg` | Spiders | Spider silhouette |
| `fungi.svg` | Fungi | Mushroom silhouette |

## Icon Requirements

### Size
- **ViewBox:** 80x80 (or will be scaled)
- Icons will be scaled to fit ~30x30 pixels in the seal centre
- Design for centre point at (40, 40)

### Format
- Simple SVG with `<path>` elements
- Single colour silhouettes work best
- No embedded styles or complex gradients
- Colour will be applied automatically by the renderer

### Example Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <path d="M40 10 L60 40 L40 70 L20 40 Z"/>
</svg>
```

## Sources

Good sources for silhouette icons:
- **PhyloPic** (https://www.phylopic.org) — CC-licensed biological silhouettes
- **SVG Silh** (https://svgsilh.com) — Public domain silhouettes
- **AI Generated** — Using DALL-E/Midjourney with "simple black silhouette" prompts

## Fallback Behaviour

If an icon file is missing:
- **General group:** Shows sun (daily) or calendar (annual) icon
- **Other groups:** Shows sun/calendar until icon is added

## Token Configuration

Icon filenames are defined in `theme.py` under `GROUP_ICONS`:

```python
GROUP_ICONS = {
    "birds": "birds.svg",
    "beetles": "beetles.svg",
    # etc.
}
```

To change a filename, just update the token in theme.py.
