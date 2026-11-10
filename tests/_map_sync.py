"""Mapping tab tests that read the map right after asking for it (R16, 10 Nov 2026).

Generate now makes the map in a worker thread (Observatum/src/views/mapping/map_job.py), so the
squares are there a moment later, not when _generate_map returns. These older tests check the
result at once: sync(tab) makes each request wait for its map. The threaded behaviour itself is
tested in test_map_job_20261110.py.
"""


def sync(tab):
    real = tab._job_request

    def request(req):
        real(req)
        tab.wait_for_map()
    tab._job_request = request
    return tab
