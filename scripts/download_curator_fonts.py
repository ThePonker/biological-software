"""
Download Victorian fonts for Curator labels.
Run once: python scripts/download_curator_fonts.py

Downloads from Google Fonts API into Curator/fonts/
"""
import urllib.request
import zipfile
import shutil
import io
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "Curator" / "fonts"

FONTS = {
    "EB Garamond": "https://fonts.google.com/download?family=EB+Garamond",
    "Libre Baskerville": "https://fonts.google.com/download?family=Libre+Baskerville",
    "Cormorant Garamond": "https://fonts.google.com/download?family=Cormorant+Garamond",
    "Libre Caslon Text": "https://fonts.google.com/download?family=Libre+Caslon+Text",
}

# Which files we need from each zip
KEEP = {
    "EB Garamond": {
        "EBGaramond-Regular.ttf": "static/EBGaramond-Regular.ttf",
        "EBGaramond-Bold.ttf": "static/EBGaramond-Bold.ttf",
        "EBGaramond-Italic.ttf": "static/EBGaramond-Italic.ttf",
        "EBGaramond-BoldItalic.ttf": "static/EBGaramond-BoldItalic.ttf",
    },
    "Libre Baskerville": {
        "LibreBaskerville-Regular.ttf": "LibreBaskerville-Regular.ttf",
        "LibreBaskerville-Bold.ttf": "LibreBaskerville-Bold.ttf",
        "LibreBaskerville-Italic.ttf": "LibreBaskerville-Italic.ttf",
    },
    "Cormorant Garamond": {
        "CormorantGaramond-Regular.ttf": "static/CormorantGaramond-Regular.ttf",
        "CormorantGaramond-Bold.ttf": "static/CormorantGaramond-Bold.ttf",
        "CormorantGaramond-Italic.ttf": "static/CormorantGaramond-Italic.ttf",
        "CormorantGaramond-BoldItalic.ttf": "static/CormorantGaramond-BoldItalic.ttf",
    },
    "Libre Caslon Text": {
        "LibreCaslonText-Regular.ttf": "static/LibreCaslonText-Regular.ttf",
        "LibreCaslonText-Bold.ttf": "static/LibreCaslonText-Bold.ttf",
        "LibreCaslonText-Italic.ttf": "static/LibreCaslonText-Italic.ttf",
    },
}


def main():
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading fonts to: {FONTS_DIR}\n")

    for family, url in FONTS.items():
        print(f"  {family}...")
        try:
            data = urllib.request.urlopen(url).read()
            z = zipfile.ZipFile(io.BytesIO(data))
            names = z.namelist()
            keep = KEEP.get(family, {})
            found = 0
            for out_name, zip_path in keep.items():
                # Try exact path first, then search by filename
                matches = [n for n in names if n.endswith(out_name) or n == zip_path]
                if matches:
                    with z.open(matches[0]) as src:
                        out_path = FONTS_DIR / out_name
                        with open(out_path, "wb") as dst:
                            dst.write(src.read())
                    found += 1
            print(f"    Extracted {found} files")
        except Exception as e:
            print(f"    ERROR: {e}")
            print(f"    Download manually from: https://fonts.google.com/specimen/{family.replace(' ', '+')}")

    # Verify
    print(f"\nInstalled fonts:")
    for f in sorted(FONTS_DIR.glob("*.ttf")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.0f} KB)")

    print(f"\nDone. Restart Curator to use the new fonts.")


if __name__ == "__main__":
    main()
