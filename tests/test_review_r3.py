"""Independent review of Round 3 (11 Oct 2026): fixes found in review."""
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_vc_label_cut_by_the_page_box_is_left_out(qapp):
    """On the atlas page the map is clipped to its box; a label crossing the box edge was
    printed half cut ('VC33)'). It is left out; a label wholly inside is kept."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter
    from shared.maps.vc_labels import draw_labels

    class Fit:
        def to_px(self, e, n):
            return e, n

    pts = [(33, (2.0, 100.0), 500.0), (23, (100.0, 100.0), 400.0)]
    img = QImage(200, 200, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.setClipRect(QRectF(0, 0, 200, 200))
    texts = {t for _vc, t, _r, _s in
             draw_labels(p, Fit(), pts, {33: "Gloucestershire", 23: "Oxon"}, span_m=1000)}
    p.end()
    assert "Oxon (VC23)" in texts
    assert not any("33" in t for t in texts)

    img = QImage(200, 200, QImage.Format.Format_ARGB32)       # no clip (screen): unchanged
    p = QPainter(img)
    texts = {t for _vc, t, _r, _s in draw_labels(p, Fit(), pts, {}, span_m=1e6)}
    p.end()
    assert {"33", "23"} <= texts


def test_batch_maps_default_folder_is_the_documents_folder():
    """Default output under the Documents folder Qt reports (OneDrive-redirected on Wil's PC),
    not a hard-coded ~/Documents."""
    import os
    from PySide6.QtCore import QStandardPaths
    from src.services.batch_maps import default_out_dir
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    out = default_out_dir("Cerambycidae")
    assert out.startswith(os.path.normpath(docs))
    assert os.path.basename(os.path.dirname(out)) == "Observatum batch maps"
