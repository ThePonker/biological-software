# Environment layers: what to download and how to build it (25 Oct 2026)

For the Mapping tab's Layers > Environment sub-menu. Nothing here has been downloaded by Claude;
page names, file names and field names were read from publishers' pages and other services' copies
of their schemas. **Unverified** marks anything not confirmed against the real file.

## Where things go

One folder: `C:\Users\<you>\Environment data\` (the default of `--source`; use `--source "path"` for
another). **Unzip every download** (the script does not read zips) into a sub-folder whose name says
what it is and, for the designations, the country: the script finds a file by the words in its
folder and file names (e.g. `SSSI England`, `SAC Wales`, `Ancient Woodland Scotland`). The folder names
below work; the publishers' own file names are not relied on. GeoPackage or shapefile; **the file must
be British National Grid (EPSG:27700)**: anything else is refused (choose "British National Grid"
when the download page asks for a projection; a shapefile needs its `.prj` beside it).

Build (PowerShell, from the project root):

```
py -3.14 scripts\build_env_layers.py                          # dry run: what it found, counts, nothing written
py -3.14 scripts\build_env_layers.py --apply                  # build everything found
py -3.14 scripts\build_env_layers.py --apply --only sssi,sac  # just some
py -3.14 scripts\build_env_layers.py --describe sssi          # columns of the files found
py -3.14 -m pip install h5py                                  # once, only for the HadUK-Grid NetCDF files
```

Files appear in `data\maps\layers\` (`<key>_gb.json`, `<key>_county.json`; grids `<key>_gb.json` + `.bin`).
If a field name is wrong the dry run says which columns the file has; correct the name in
`scripts\env_sources.py` (one table). Credits of ticked layers are added to the atlas page footer.

## Licence note

Most of these are Open Government Licence v3.0 (attribution required). The exceptions:

- **Soilscapes** (Cranfield University / LandIS) requires a licence (data.gov.uk: "subject to a specific
  licensing agreement", commercial charges); kept hidden. Its Layers item is hidden unless the setting
  `mapping/allow_soilscapes` is on.
- **Ancient Woodland Inventory, Scotland** (NatureScot) is under the **OS Open Data licence**, not the OGL;
  credit: "Copyright NatureScot. Contains Ordnance Survey data © Crown copyright and database right [year]."
- **Living England Habitat Map (Phase 4)** has its own data.gov.uk attribution statement (env_registry.C_LE;
  only the opening could be fetched, complete it from the dataset page).
- **Forestry Commission NFI**, **BGS** geology/soils and the **Met Office** HadUK-Grid carry their own
  credit lines (env_registry.py); the Met Office and Forestry Commission ones are OGL, BGS is BGS terms.
- The OS sentence ("Contains OS data © Crown copyright and database right [year]") is added once per page.

| Layer key | Dataset | Download from | Pick | Folder (inside Environment data) | Credit line shown |
|---|---|---|---|---|---|
| sssi | SSSI, England | Defra Data Services Platform, search "Sites of Special Scientific Interest (England)" (environment.data.gov.uk, "Natural England Open Data Geoportal") | Shapefile or GeoPackage, whole of England, British National Grid | `SSSI England` | NE |
| sssi | SSSI, Wales | DataMapWales (datamap.gov.wales), layer "NRW SSSI" (unverified name) | Shapefile / GPKG, EPSG:27700 | `SSSI Wales` | NRW |
| sssi | SSSI, Scotland | NatureScot Open Data Hub (opendata.nature.scot), "Sites of Special Scientific Interest - Scotland" | Shapefile / GPKG, EPSG:27700 | `SSSI Scotland` | NatureScot |
| sac, spa, ramsar, nnr, lnr | Same three sources for each type: "Special Areas of Conservation", "Special Protection Areas", "Ramsar", "National Nature Reserves", "Local Nature Reserves" | as above | as above | `SAC England`, `SPA Wales`, `Ramsar Scotland`, `NNR England`, `LNR Wales` ... | as above |
| ancient_woodland | Ancient Woodland Inventory | England: Defra Data Services Platform "Ancient Woodland (England)"; Wales: DataMapWales "Ancient Woodland Inventory"; Scotland: NatureScot "Ancient Woodland Inventory" | Shapefile / GPKG, 27700 | `Ancient Woodland England` / `Wales` / `Scotland` | NE, NRW, NatureScot |
| wood_pasture | Wood-pasture and Parkland (England) | Defra Data Services Platform | Shapefile / GPKG | `Wood-pasture England` | NE |
| geology_bedrock, geology_superficial | BGS Geology 625k (DiGMapGB-625), bedrock and superficial | BGS "Geology 625k" open data downloads (bgs.ac.uk, Datasets: "BGS Geology 625k (DiGMapGB-625)") | Shapefile, BNG; the bedrock and superficial polygon files (not dykes, faults, linear features) | `BGS 625k bedrock`, `BGS 625k superficial` | BGS |
| soil_pm | BGS Soil Parent Material Model, 1 km, GB | BGS Datasets > "Soil Parent Material Model" (bgs.ac.uk/datasets/soil-parent-material-model); the 1 km version is the open one (check the terms on the page: unverified) | Shapefile / GPKG | `Soil Parent Material 1km` | BGS |
| haduk_rain, haduk_temp, haduk_sun, haduk_frost | Met Office HadUK-Grid 1991-2020 long-term averages, 1 km, annual | CEDA catalogue "HadUK-Grid gridded and regional average climate observations for the UK" (catalogue.ceda.ac.uk/uuid/4dc8450d889a491ebb20e724debe2dfb); files under `.../HadUK-Grid/v1.3.2.ceda/` (the latest at the time) in `1km/<variable>/ann-30y/` (path unverified); free CEDA login | NetCDF, 1 km, annual 30-year averages 1991-2020: variables `rainfall`, `tas`, `sun`, `groundfrost`, e.g. `rainfall_hadukgrid_uk_1km_ann-30y_199101-202012.nc` (name unverified) | `HadUK-Grid` (all four files) | Met Office |
| phi | Priority Habitat Inventory (England) | Defra Data Services Platform "Priority Habitats Inventory (England)" | GeoPackage / shapefile; very large | `Priority Habitat Inventory England` | NE |
| nfi | National Forest Inventory Woodland GB 2023 | Forestry Commission Open Data (data-forestry.opendata.arcgis.com) "National Forest Inventory Woodland GB 2023" | Shapefile / GPKG | `National Forest Inventory 2023` | FC |
| soilscapes | Soilscapes (LandIS, Cranfield), England and Wales | landis.org.uk, Soilscapes; **requires a licence (kept hidden)** | Shapefile, BNG | `Soilscapes` | Cranfield |
| crow_access | CRoW Act 2000 Access Layer (open country + registered common land combined) | Defra Data Services Platform "CRoW Act 2000 - Access Layer" | Shapefile / GPKG | `CRoW Access England` | NE |
| common_land | Registered common land | Built from the CRoW Access Layer above (its RCL = Yes areas); nothing extra to download | - | (`CRoW Access England`) | NE |
| living_england | Living England Habitat Map, Phase 4 | Defra Data Services Platform "Living England Habitat Map (Phase 4)" | GeoPackage or shapefile (not the file geodatabase); very large | `Living England` | NE |

## Fields read (see scripts\env_sources.py)

| Key | Name `n` | Class `t` | Status |
|---|---|---|---|
| sssi England | `SSSI_NAME` | fixed "SSSI" | verified (NE schema as copied by councils) |
| nnr, lnr England | `NNR_NAME`, `LNR_NAME` | fixed type | verified (same) |
| sac, spa, ramsar England | `SAC_NAME`, `SPA_NAME`, `RAMSAR_NAME` | fixed type | unverified guess (falls back to `NAME` / any column with "name") |
| every designation, Wales and Scotland | `NAME`, `SITE_NAME`, `SSSI_NAME` | fixed type | unverified guess |
| ancient_woodland England | `NAME` | `THEMNAME` (else `THEME`) turned into ASNW / ARW / PAWS / AWSUC | field names verified (council copy); wording of the values partly unverified, unrecognised text is kept as it is |
| ancient_woodland Wales | none (NRW's file has no name) | `category_n`, turned into ASNW / RAWS / PAWS / AWSUC; the 2 "... Deleted" rows left out | verified 25 Oct 2026 (NRW AWI 2021) |
| ancient_woodland Scotland | `SITE_NAME` | `ANTIQUITY`, kept as written: Ancient (of semi-natural origin) / Long-Established (of plantation origin) / Other (on Roy map) | verified 25 Oct 2026 |
| wood_pasture | none | `mainhabs` (one value, "Wood pasture and parkland"); the file's name contains "Priority_Habitat_Inventory", so the phi layer ignores wood-pasture files | verified 25 Oct 2026 |
| geology_bedrock | `LEX_D` (rock unit) | `RCS_D` (lithology) | verified (BGS 625k service schema) |
| geology_superficial | `LEX_D` | `RCS_D` | unverified (same fields assumed) |
| soil_pm | `SOIL_TEX` (else `PMM_GRAIN`, `ESB_DESC`) | `CARB_CNTNT` as "carbonate Mod" | field names verified (BGS Open Report OR/14/025); the 1 km file's own column spelling unverified; neighbouring squares with the same texture and carbonate are joined |
| soilscapes | `SOILSCAPE_DESC`, `DESC_` ... | `SOILSCAPE` as "Soilscape 6" | unverified guess |
| phi | none | `MainHabs` / `Main_Habit` | field seen in council copies; shapefile spelling unverified |
| nfi | none | `IFT_IOA` (else `IFT`, `CATEGORY`) | `IFT_IOA` is the Forestry Commission's name for "interpreted forest type / interpreted open area"; verify |
| living_england | none | `Prim_Hab` and variants | unverified guess |
| crow_access | none | `ACCESS_TYP` ... else "Access land" | unverified guess |
| common_land | `NAME` ... | none | unverified guess |
| HadUK grids | - | variables `rainfall` (mm), `tas` (degC), `sun` (hours), `groundfrost` (days) | unverified; the file's grid_mapping is checked to be the British National Grid, else refused |

## Size and speed

PHI, NFI and Living England are built at county detail only (no GB file; they are not drawn or
identified in the GB-wide view) and are large (whole-England PHI is hundreds of thousands of polygons;
NFI over a million). `--types "Deciduous woodland,Lowland fens"` on `--only phi` keeps just those main
habitats (matched exactly, case ignored). A county file over 150 MB is refused unless `--allow-large`
is given (narrow it with `--types`); a subset never overwrites an existing full `phi` file unless
`--replace` is given. If a source has both a .shp and a .gpkg copy, only the .gpkg is read. The first draw of a big county file takes a while to load.

## Checked against the real downloads (25 Oct 2026)

- BGS 625k comes as one GeoPackage (`625k_V5_Geology_UK_EPSG27700.gpkg`) with bedrock, superficial, dyke and fault tables; its bedrock table uses BGS's own srs id 100000, whose definition is the British National Grid, so it is accepted (a custom id that is not BNG is still refused). The table is chosen by all the words of the layer ("625k" and "bedrock").
- CRoW Access Layer: Yes/No fields `oc`, `rcl`, `s16`; an area's class is the ones set, e.g. "Open country + Registered common land" ("Access land" when none is). The common_land layer is the `rcl` = Yes areas.
- Designations: England `name` / `sac_name` / `spa_name`; Wales `sssi_name`, `lnr_name`; Scotland `NAME` were found.
- GeoJSON is not read (DataMapWales' SPA GeoJSON held 4 sites only; Living England offered as GeoJSON): use the shapefile or GeoPackage.
