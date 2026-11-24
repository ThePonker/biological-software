"""24 Nov 2026: the specimens pill has its own line, so it can't be folded into a bare "+1"."""
from types import SimpleNamespace

from PySide6.QtWidgets import QLabel

from tests.test_dataentry_r3 import qapp  # noqa: F401


def test_specimen_pill_on_its_own_row(qapp):  # noqa: F811
    from DataEntry.info_panel import InfoPanel, _FlowRow
    svc = SimpleNamespace(counts=lambda tvk: (27, 6, 3), specimen_sexes=lambda tvk: (2, 1, 0))
    fake = SimpleNamespace(_svc=svc, _pending_for=lambda tvk: {"personal": 0, "commercial": 1},
                           _pill=lambda t: QLabel(t), _pills_row=_FlowRow(), _spec_row=_FlowRow())
    InfoPanel._set_count_pills(fake, "NBNSYS0000000001")
    assert [w.text() for w in fake._pills_row._items] == ["Pers. 27", "Comm. 6 (+1)"]
    assert [w.text() for w in fake._spec_row._items] == ["Spec. 3 (\u26422 \u26401)"]
