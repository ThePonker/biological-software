"""Colour tokens for the shared map widgets -- the one place they come from.

The maps were built inside Data Entry and draw with its tokens, which resolve from
Observatum's Naturalist theme when Observatum is running (and fall back to the same
values standalone). Re-using that resolver keeps the maps looking identical in Data
Entry, the Add Specimen dialog and the Mapping tab, without a fifth copy of the palette.
"""
from DataEntry import theme  # noqa: F401  (re-export)
