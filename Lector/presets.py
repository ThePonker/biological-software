"""Built-in journal presets: whole-word title filters (see harvest.title_has).

Copied into journal_presets when lector.db is created or updated; Wil can edit
them there (service.save_preset) without touching this file. A search copies a
preset's words into its own filters, so later edits to a preset never change
what an earlier run did.

English plurals match ('Naturalist' finds "Naturalists' Society"), foreign
forms do not ('naturalistes', 'Naturalista').
"""

BUILTIN_PRESETS = [
    {
        "name": "British periodicals",
        "description": "The main British entomological and natural-history journals "
                       "(Entomologist's Monthly Magazine, The Entomologist, Annals and "
                       "Magazine of Natural History, The Zoologist, county Transactions "
                       "and Proceedings). Journals of North America, Australia and India "
                       "left out.",
        "include": ["Entomologist", "Naturalist", "Zoologist", "British", "Transactions",
                    "Annals", "Proceedings"],
        "exclude": ["Canadian", "American", "America", "Australia", "Australian",
                    "India", "Indian", "New Zealand", "South African"],
    },
    {
        "name": "Scottish titles",
        "description": "Scottish journals and societies: Scottish Naturalist, Annals of "
                       "Scottish Natural History, Glasgow and Edinburgh societies, "
                       "Perthshire, Berwickshire, Dumfriesshire and Galloway.",
        "include": ["Scottish", "Scotland", "Glasgow", "Edinburgh", "Perthshire",
                    "Berwickshire", "Dumfriesshire", "Galloway", "Aberdeen", "Dundee",
                    "Inverness", "Highland"],
        "exclude": [],
    },
]
