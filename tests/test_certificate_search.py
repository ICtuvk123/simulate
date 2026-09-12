import json, math, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from certificate_search import CertificateSearch
from q4controller import Q4Controller
from q4engine import Session, Source
from q3client import Client, canonical, ProtocolError
from test_shared_stops import Journal


class CertificateSearchTests(unittest.TestCase):
    def controller(self, signal=False, reject=False):
        scene = Session(sources=[Source(20 if signal else 1, 500, 0, 1500)])
        def transport(path, body, timeout):
            if reject and path == '/measure':
                return 400, canonical(dict(accepted=False, error='unit_rejection'))
            status, response = scene.handle(path, body)
            return status, canonical(response)
        client = Client('local-robot', Journal(), transport=transport)
        options = json.loads((Path(__file__).resolve().parents[1] /
                              'configs/D_compact_optical.json').read_text())
        c = Q4Controller(client, options)
        client.action('/enter')
        c.empty = set(range(1, 20))
        r, a = (1000., 0.), (0., 1000.)
        c.remaining = [r, a]
        manager = CertificateSearch([r, a], {})
        c.certificate_search = manager
        manager.prove = lambda sites: dict(complete=(0., 0.) in sites and a in sites,
                                          kind='unit_route_geometry')
        plan = dict(group=(r,), changes={20: ({r}, True)}, needed=[20],
                    whole=True, move_saved=40., gain=40.)
        return c, manager, plan, r, a

    def test_planned_points_do_not_become_actual_negatives_or_empty(self):
        c, m, plan, r, a = self.controller()
        self.assertEqual(c.negatives[20], [])
        m._execute(c, (0., 0.), plan)
        self.assertEqual(c.negatives[20], [(0., 0.)])
        self.assertNotIn(20, c.empty)
        self.assertEqual(c.remaining, [a])
        self.assertFalse(m.needs(20, r))
        row = next(row for row in c.client.journal.rows
                   if row.get('reason') == 'q4_certificate_sites_removed')
        self.assertEqual(row['actual_scanned_channels'],
                         [dict(channel=20, result='no_signal')])
        witness = row['route_redundancy_witness'][20]
        self.assertEqual(witness['actual_negative_sites'], [(0., 0.)])
        self.assertEqual(witness['remaining_planned_sites'], [a])

    def test_rejected_action_cannot_cancel_requirement(self):
        c, m, plan, r, a = self.controller(reject=True)
        with self.assertRaises(ProtocolError):
            m._execute(c, (0., 0.), plan)
        self.assertEqual(c.negatives[20], [])
        self.assertEqual(c.remaining, [r, a])
        self.assertTrue(m.needs(20, r))

    def test_forecast_point_cannot_trigger_a_replacement_scan(self):
        c, m, plan, r, a = self.controller()
        before = len(c.client.ledger.events)
        with self.assertRaises(ValueError):
            m._execute(c, (100., 100.), plan)
        self.assertEqual(len(c.client.ledger.events), before)
        self.assertEqual(c.remaining, [r, a])

    def test_candidate_budget_preserves_singletons_and_station_groups(self):
        c, m, plan, r, a = self.controller()
        from directional_geometry import skeleton
        c.remaining = skeleton()[1:]
        m.required[20] = set(c.remaining)
        plans = m._plans(c, (800., 10.), [20])
        self.assertLessEqual(len(plans), 18)
        self.assertEqual({len(plan[2]) for plan in plans}, {1, 2, 3})

    def test_positive_replacement_discovers_source_and_does_not_claim_empty(self):
        c, m, plan, r, a = self.controller(signal=True)
        m._execute(c, (0., 0.), plan)
        self.assertIn(20, c.polygons)
        self.assertNotIn(20, c.empty)
        self.assertEqual(c.negatives[20], [])
        self.assertFalse(c.cleared)

    def test_geometry_budget_is_deterministic_and_unproved_is_not_accepted(self):
        m = CertificateSearch([], {})
        self.assertTrue(math.isinf(m.prover.time_budget))
        self.assertFalse(m.prove([(0, 0), (10, 0), (0, 10)])['complete'])
        from directional_geometry import skeleton
        m.prover.max_cells = 1
        self.assertFalse(m.prove(skeleton())['complete'])

    def test_inactive_default_has_no_scan_requirements_override(self):
        c, m, plan, r, a = self.controller()
        self.assertFalse(c.options.get('certificate_replace', False))


if __name__ == '__main__':
    unittest.main()
