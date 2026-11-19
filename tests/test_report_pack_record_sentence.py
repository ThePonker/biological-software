"""Report pack species accounts: a species' records as one readable sentence."""
from Examen.report_pack_tables import (count_text, determiner_text, method_text,
                                       record_sentence)


def test_single_record_with_determiner_inside():
    r = [("2026-07-14", "SK 510 430", "Net", 1, "Falk, S.J.")]
    assert record_sentence(r) == "Recorded on 14 July 2026 at SK 510 430 (one, net; det. S.J. Falk)."


def test_two_places_same_day_same_determiner_once_at_end():
    r = [("2026-07-14", "SK 51083 43015", "Pitfall trap", "1", "Heeney, W.J."),
         ("2026-07-14", "SK 510 430", "Net", 3, "Heeney, W.J.")]
    assert record_sentence(r) == ("Recorded on 14 July 2026 at SK 51083 43015 (one, pitfall trap) "
                                  "and at SK 510 430 (three, net); det. W.J. Heeney.")


def test_several_dates():
    r = [("2026-05-26", "SK 1 1", "net", 2, ""), ("2026-06-14", "SK 2 2", "pitfall trap", 12, ""),
         ("2026-07-01", "SK 3 3", "", None, "")]
    assert record_sentence(r) == ("Recorded on 26 May 2026 at SK 1 1 (two, net); "
                                  "on 14 June 2026 at SK 2 2 (12, pitfall trap); "
                                  "and on 1 July 2026 at SK 3 3.")


def test_different_determiners_stay_with_their_group():
    r = [("2026-05-26", "SK 1 1", "net", 1, "Falk, S.J."), ("2026-06-14", "SK 2 2", "net", 1, "")]
    assert record_sentence(r) == ("Recorded on 26 May 2026 at SK 1 1 (one, net; det. S.J. Falk); "
                                  "and on 14 June 2026 at SK 2 2 (one, net).")


def test_same_place_two_methods_one_group():
    r = [("2026-05-26", "SK 1 1", "Net", 1, "Smith"), ("2026-05-26", "SK 1 1", "Pitfall trap", 3, "Smith")]
    assert record_sentence(r) == ("Recorded on 26 May 2026 at SK 1 1 "
                                  "(one, net; three, pitfall trap; det. Smith).")


def test_missing_parts_left_out():
    assert record_sentence([("2026-05-26", "SK 1 1", "Field observation", None, "")]) == \
        "Recorded on 26 May 2026 at SK 1 1 (field observation)."
    assert record_sentence([("2026-05-26", "", "", 1, "")]) == "Recorded on 26 May 2026 (one)."
    assert record_sentence([("", "SK 1 1", "", None, "")]) == "Recorded at SK 1 1."
    assert record_sentence([]) == ""


def test_helpers():
    assert [count_text(x) for x in (1, "10", 11, 3.0, "c. 20", None, "")] == \
        ["one", "ten", "11", "three", "c. 20", "", ""]
    assert method_text("UV Light trap") == "UV light trap"
    assert determiner_text("Falk, S.J.") == "S.J. Falk"
    assert determiner_text("A. Smith") == "A. Smith"


def test_differing_determiners_in_one_group_stay_with_their_records():
    s = record_sentence([("2026-07-14", "SK 510 430", "Net", 1, "Heeney, W.J."),
                           ("2026-07-14", "SK 510 430", "Pitfall trap", 2, "Moore, J."),
                           ("2026-07-14", "SK 510 430", "Net", 3, "")])
    assert s == ("Recorded on 14 July 2026 at SK 510 430 (one, net, det. W.J. Heeney; "
                 "two, pitfall trap, det. J. Moore; three, net).")


def test_placeholder_methods_and_several_determiners():
    assert method_text("Other method (add comment)") == "" and method_text("Unknown") == ""
    assert determiner_text("Falk, S.J.; Heeney, W.J.") == "S.J. Falk and W.J. Heeney"
    assert record_sentence([("", "", "", "", "")]) == "Recorded (no date, place or method held)."


def test_status_key_string_kept_as_made():
    from Examen import status_marks as sm
    assert sm._as_key("NA") == "NA" and sm._as_key("vu; NA") == "NA; VU"
