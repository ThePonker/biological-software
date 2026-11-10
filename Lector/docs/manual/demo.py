"""A small made-up lector.db for the manual's screenshots: invented searches, pages and text,
no network, nothing from Wil's data. Used by make_screens.py (and its test)."""
import sqlite3
from pathlib import Path

from Lector.service import LectorService

TEXTOR, SUTOR = "NBNSYS0000011050", "NHMSYS0020704741"
FILTERS = {"include_words": ["Entomologist", "Annals", "Transactions"],
           "exclude_words": ["Canadian"], "max_pages": 0}


def _page(pid, num, ptype="Text"):
    return {"PageID": pid, "PageNumbers": [{"Prefix": "Page", "Number": str(num)}],
            "PageTypes": [{"PageTypeName": ptype}]}


def _item(iid, volume, year, *pages):
    return {"ItemID": iid, "Volume": volume, "Year": str(year), "Pages": list(pages)}


TEXTS = {
    101: "Lamia textor. I took one female of the Weaver beetle on 14th June last, on a willow "
         "stump in Darenth Wood, near Dartford. Mr. J. Smith had taken it there before.",
    102: "The longhorn beetles of the northern counties were examined with care. Lamia textor "
         "occurred sparingly with Saperda populnea at Rannoch, on felled willow, in July 1868.",
    103: "Lamia textor, Linn. Taken at Aviemore by Mr. H. Brown in 1879; det. E. A. Waterhouse.",
    104: "Lamia textor is recorded from the fens near Cambridge, where it is said to be rare.",
    105: "Notes on Coleoptera. Lamia textor was beaten from sallow at Wicken Fen, Cambs., "
         "on 2nd June 1884, two specimens, by the Rev. T. Wilkinson.",
    106: "Dealer in natural history specimens. Lamia textor 2 fr., Carabus auratus 1 fr.",
    201: "Monochamus sutor was taken at Perth by Mr. Gray, a single male, in August 1850.",
    202: "Monochamus sutor again, at Dunkeld, among pine logs, in 1851.",
}


def bhl_data():
    textor = [{"NameConfirmed": "Lamia textor", "Titles": [
        {"TitleID": 1, "FullTitle": "The Entomologist's monthly magazine", "Items": [
            _item(10, "v.4 (1867-1868)", 1868, _page(101, 81), _page(102, 145)),
            _item(11, "v.21 (1884-1885)", 1884, _page(105, 41))]},
        {"TitleID": 2, "FullTitle": "The Annals and magazine of natural history", "Items": [
            _item(20, "v.3 (1879)", 1879, _page(103, 77))]},
        {"TitleID": 3, "FullTitle": "Transactions of the Entomological Society of London",
         "Items": [_item(30, "1890", 1890, _page(104, 12))]},
        {"TitleID": 4, "FullTitle": "Le Naturaliste", "Items": [
            _item(40, "14", 1900, _page(106, 38, "Advertisement"))]}]}]
    sutor = [{"NameConfirmed": "Monochamus sutor", "Titles": [
        {"TitleID": 5, "FullTitle": "The Entomologist's weekly intelligencer", "Items": [
            _item(50, "1", 1856, _page(201, 5), _page(202, 6))]}]}]
    return {"Lamia textor": textor, "Monochamus sutor": sutor}


class DemoBHL:
    """BHLClient stand-in: answers from the invented data above, instantly."""
    request_count, _interval = 0, 0

    def __init__(self):
        self.names = bhl_data()

    def name_metadata(self, name):
        return self.names.get(name, [])

    def page_metadata(self, pid):
        return {"PageID": pid, "OcrText": TEXTS.get(pid, ""), "TextSource": "OCR",
                "Names": []}

    def check_key(self):
        return []


def make_uksi(path):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, family TEXT,
                           genus TEXT, sort_code INTEGER);
        CREATE TABLE synonyms (synonym TEXT, tvk TEXT);
        CREATE TABLE name_map (tvk TEXT PRIMARY KEY, recommended_tvk TEXT, name TEXT,
                               recommended_name TEXT, name_status TEXT);""")
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?)", [
        (TEXTOR, "Lamia textor", "Species", "Cerambycidae", "Lamia", 1),
        (SUTOR, "Monochamus sutor", "Species", "Cerambycidae", "Monochamus", 2),
        ("NHMSYS0099000001", "Cerambycidae", "Family", "Cerambycidae", "", 0)])
    c.execute("INSERT INTO synonyms VALUES ('Cerambyx textor', ?)", (TEXTOR,))
    c.commit()
    c.close()


def build(folder):
    """Make the demo database in `folder`; returns (service, {'lamia': id, 'sutor': id})."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    uksi = folder / "uksi.db"
    make_uksi(uksi)
    fake = DemoBHL()
    svc = LectorService(db_path=folder / "lector.db", uksi_db=uksi, client_factory=lambda: fake,
                        export_dir=folder / "exports", synonym_file=folder / "synonyms.txt",
                        backup_dir=folder / "_backups", key_client_factory=lambda _k: fake)
    lam = svc.create_search("Lamia textor", name="Lamia textor - British literature",
                            names=["Lamia textor"], filters=FILTERS)
    sut = svc.create_search("Monochamus sutor", name="Monochamus sutor",
                            names=["Monochamus sutor"], filters=FILTERS)
    svc.run_search(lam)
    svc.run_search(sut)
    pages = {p["year"]: p["page_id"] for p in svc.review_queue(lam)}
    key = svc.add_tag("Locality given")
    marks = ((1868, "relevant", "record"), (1879, "record_extracted", key),
             (1884, "record_extracted", "record"), (1890, "not_relevant", None),
             (1900, "not_relevant", "index"))
    for year, status, tag in marks:
        pid = next((v for k, v in pages.items() if k == year), None)
        if pid:
            svc.set_review(lam, pid, status=status, tag=tag)
    first = svc.review_queue(lam)[0]
    svc.set_review(lam, first["page_id"], notes="Darenth Wood is near Dartford: check the grid.")
    for p in svc.review_queue(lam):
        if p["year"] in (1879, 1884):
            svc.add_record(lam, p["page_id"], _record(svc, lam, p))
    svc.export(lam, formats=("txt",))
    return svc, {"lamia": lam, "sutor": sut}


def _record(svc, sid, page):
    f = svc.record_prefill(sid, page["page_id"])
    if page["year"] == 1879:
        f.update(date_printed="1879", year=1879, place="Aviemore, Inverness-shire",
                 vice_county=96, recorder="Mr. H. Brown", determiner="E. A. Waterhouse",
                 count="1", comment="Taken at Aviemore.")
    else:
        f.update(date_printed="2nd June 1884", day=2, month=6, year=1884,
                 place="Wicken Fen, Cambs.", grid_ref="TL5570", vice_county=29,
                 recorder="Rev. T. Wilkinson", count="two", stage="adult",
                 comment="Beaten from sallow.")
    return f
