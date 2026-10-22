import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import legacy_publish as publisher


class ActionsPublicationGateTests(unittest.TestCase):
    def test_only_master_protected_environment_can_supply_secret(self):
        env = {
            'GITHUB_ACTIONS': 'true',
            'GITHUB_REF': 'refs/heads/master',
            'GT030_PUBLISH_ENVIRONMENT': 'legacy-publish',
            'SAKURA_FTPS_PASSWORD': 'synthetic-secret',
        }
        self.assertEqual(publisher.actions_credential(env), 'synthetic-secret')
        for key, value in [('GITHUB_ACTIONS', 'false'), ('GITHUB_REF', 'refs/heads/topic'),
                           ('GT030_PUBLISH_ENVIRONMENT', 'other')]:
            altered = dict(env, **{key: value})
            with self.subTest(key=key), self.assertRaises(publisher.Stop):
                publisher.actions_credential(altered)

    def test_missing_secret_stops_before_network_setup(self):
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/master',
               'GT030_PUBLISH_ENVIRONMENT': 'legacy-publish'}
        with self.assertRaises(publisher.Stop):
            publisher.actions_credential(env)


if __name__ == '__main__':
    unittest.main(verbosity=2)
