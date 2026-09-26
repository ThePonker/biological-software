"""check_research_only.py -- verify the S41 "research only" moth list against your data.

    python scripts/check_research_only.py

Source
------
Butterfly Conservation, "The UK Biodiversity Action Plan - moths", Table 4:
"UK BAP species (common and widespread, but rapidly declining moths) added by
the 2007 review - RESEARCH ONLY". 71 species.

These are common, widespread moths added to the UK BAP -- and thence to NERC
S.41 -- on the strength of Rothamsted decline data, NOT rarity. Butterfly
Conservation's own wording:

    "There is clearly potential for confusion with the listing of the rapidly
    declining species, as many are still 'common' and 'widespread' and can occur
    in many recorders own back gardens... These species will not be treated
    through formal individual Action Plans and are NOT INTENDED TO PLAY A ROLE
    IN SITE PROTECTION."

That last sentence is the justification for excluding them from a site's key
species count.

Two caveats from the source document
------------------------------------
1. Butterfly Conservation notes that Large Wainscot (Rhizedra lutosa) and
   White-line Dart (Euxoa tritici) "are missing from the formal listing signed
   up to by the ministers", though they qualify. They are in Table 4 but may not
   be on S41. Flagged below.
2. Names are as published in 2007. Several have since changed genus. This script
   resolves each against UKSI and reports the current name, so the list can be
   keyed on TVK rather than on a name that has moved.

This script only reports. It writes nothing.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402

# Butterfly Conservation, UK BAP moths, Table 4 -- "Research only", 71 species.
# (2007 names as published.)
RESEARCH_ONLY = [
    ("Hepialus humuli", "Ghost Moth"),
    ("Trichiura crataegi", "Pale Eggar"),
    ("Malacosoma neustria", "Lackey"),
    ("Watsonalla binaria", "Oak Hook-tip"),
    ("Cymatophorima diluta", "Oak Lutestring"),
    ("Hemistola chrysoprasaria", "Small Emerald"),
    ("Timandra comae", "Blood-vein"),
    ("Scopula marginepunctata", "Mullein Wave"),
    ("Orthonama vittata", "Oblique Carpet"),
    ("Xanthorhoe decoloraria", "Red Carpet"),
    ("Xanthorhoe ferrugata", "Dark-barred Twin-spot Carpet"),
    ("Scotopteryx chenopodiata", "Shaded Broad-bar"),
    ("Epirrhoe galiata", "Galium Carpet"),
    ("Entephria caesiata", "Grey Mountain Carpet"),
    ("Pelurga comitata", "Dark Spinach"),
    ("Eulithis mellinata", "Spinach"),
    ("Ecliptopera silaceata", "Small Phoenix"),
    ("Melanthia procellata", "Pretty Chalk Carpet"),
    ("Perizoma albulata", "Grass Rivulet"),
    ("Chesias legatella", "Streak"),
    ("Chesias rufata", "Broom-tip"),
    ("Macaria wauaria", "V-moth"),
    ("Chiasmia clathrata", "Latticed Heath"),
    ("Ennomos quercinaria", "August Thorn"),
    ("Ennomos fuscantaria", "Dusky Thorn"),
    ("Ennomos erosaria", "September Thorn"),
    ("Lycia hirtaria", "Brindled Beauty"),
    ("Diloba caeruleocephala", "Figure of Eight"),
    ("Arctia caja", "Garden Tiger"),
    ("Spilosoma lubricipeda", "White Ermine"),
    ("Spilosoma luteum", "Buff Ermine"),
    ("Tyria jacobaeae", "Cinnabar"),
    ("Euxoa tritici", "White-line Dart"),            # see caveat 1
    ("Euxoa nigricans", "Garden Dart"),
    ("Eugnorisma glareosa", "Autumnal Rustic"),
    ("Diarsia rubi", "Small Square-spot"),
    ("Xestia castanea", "Neglected Rustic"),
    ("Xestia agathina", "Heath Rustic"),
    ("Graphiphora augur", "Double Dart"),
    ("Melanchra persicariae", "Dot Moth"),
    ("Melanchra pisi", "Broom Moth"),
    ("Tholera cespitis", "Hedge Rustic"),
    ("Tholera decimalis", "Feathered Gothic"),
    ("Orthosia gracilis", "Powdered Quaker"),
    ("Mythimna comma", "Shoulder-striped Wainscot"),
    ("Brachylomia viminalis", "Minor Shoulder-knot"),
    ("Asteroscopus sphinx", "Sprawler"),
    ("Dasypolia templi", "Brindled Ochre"),
    ("Aporophyla lutulenta", "Deep-brown Dart"),
    ("Allophyes oxyacanthae", "Green-brindled Crescent"),
    ("Blepharita adusta", "Dark Brocade"),
    ("Agrochola helvola", "Flounced Chestnut"),
    ("Agrochola litura", "Brown-spot Pinion"),
    ("Agrochola lychnidis", "Beaded Chestnut"),
    ("Atethmia centrago", "Centre-barred Sallow"),
    ("Xanthia icteritia", "Sallow"),
    ("Xanthia gilvago", "Dusky-lemon Sallow"),
    ("Acronicta psi", "Grey Dagger"),
    ("Acronicta rumicis", "Knot Grass"),
    ("Amphipyra tragopoginis", "Mouse Moth"),
    ("Apamea remissa", "Dusky Brocade"),
    ("Apamea anceps", "Large Nutmeg"),
    ("Mesoligia literosa", "Rosy Minor"),
    ("Amphipoea oculea", "Ear Moth"),
    ("Hydraecia micacea", "Rosy Rustic"),
    ("Celaena haworthii", "Haworth's Minor"),
    ("Celaena leucostigma", "Crescent"),
    ("Rhizedra lutosa", "Large Wainscot"),           # see caveat 1
    ("Hoplodrina blanda", "Rustic"),
    ("Caradrina morpheus", "Mottled Rustic"),
    ("Stilbia anomala", "Anomalous"),
]

NOT_IN_MINISTERIAL_LISTING = {"Euxoa tritici", "Rhizedra lutosa"}


def main():
    print(f"\nS41 'research only' moths -- Butterfly Conservation Table 4")
    print("=" * 78)
    print(f"  species in the published list: {len(RESEARCH_ONLY)}")

    uk = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    uk.row_factory = sqlite3.Row
    cx = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    ob = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

    resolved, unresolved, on_s41, not_on_s41, recorded = [], [], [], [], []

    for name, common in RESEARCH_ONLY:
        row = uk.execute(
            "SELECT tvk, scientific_name FROM taxa WHERE LOWER(scientific_name)=LOWER(?) LIMIT 1",
            (name,)).fetchone()
        if not row:
            row = uk.execute(
                "SELECT t.tvk, t.scientific_name FROM synonyms s JOIN taxa t ON t.tvk = s.tvk "
                "WHERE LOWER(s.synonym)=LOWER(?) LIMIT 1", (name,)).fetchone()
        if not row:
            unresolved.append((name, common))
            continue

        tvk, current = row["tvk"], row["scientific_name"]
        resolved.append((name, common, tvk, current))

        s41 = cx.execute(
            "SELECT 1 FROM status_summary WHERE tvk=? AND status_track='priority' "
            "AND status_value LIKE '%S.41%' LIMIT 1", (tvk,)).fetchone()
        (on_s41 if s41 else not_on_s41).append((name, common, current))

        n = ob.execute("SELECT COUNT(*) FROM observations WHERE species_tvk=?",
                       (tvk,)).fetchone()[0]
        if n:
            recorded.append((current, common, n, bool(s41)))

    print(f"  resolved against UKSI:        {len(resolved)}")
    print(f"  NOT resolved:                 {len(unresolved)}")
    print(f"  carry S.41 in your Codex:     {len(on_s41)}")
    print(f"  do NOT carry S.41:            {len(not_on_s41)}")

    if unresolved:
        print("\n  ** could not resolve -- check these names **")
        for n, c in unresolved:
            print(f"     {n:34} {c}")

    changed = [(o, cur, c) for o, c, _t, cur in resolved if o.lower() != cur.lower()]
    if changed:
        print(f"\n  names changed since 2007 ({len(changed)}) -- list is keyed on TVK, so this is fine:")
        for old, cur, c in changed:
            print(f"     {old:30} -> {cur:32} {c}")

    if not_on_s41:
        print(f"\n  in Table 4 but NOT flagged S.41 in your Codex ({len(not_on_s41)}):")
        for n, c, cur in not_on_s41:
            flag = "  <- BC notes this is missing from the ministerial listing" \
                if n in NOT_IN_MINISTERIAL_LISTING else ""
            print(f"     {cur:32} {c}{flag}")

    print(f"\n  RECORDED BY YOU ({len(recorded)} species):")
    print(f"    {'species':32} {'common name':30} {'records':>8}  S41?")
    for cur, c, n, s41 in sorted(recorded, key=lambda r: -r[2]):
        print(f"    {cur:32} {c:30} {n:>8}  {'yes' if s41 else 'no'}")
    print(f"\n    total records affected: {sum(r[2] for r in recorded):,}")
    print("\n  Nothing has been changed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
