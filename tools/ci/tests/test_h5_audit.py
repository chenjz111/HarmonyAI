"""The compiler can acknowledge known BLOCKED probes, never allowed network."""
import unittest
from tools.ci.run_h5 import validate_compiler_denials


class CompilerAuditTests(unittest.TestCase):
    def test_known_discovery_probes_are_still_blocked(self):
        self.assertTrue(validate_compiler_denials(
            [{'api':'child_process.spawnSync','action':'blocked'},{'api':'child_process.exec','action':'blocked'}],
            [{'api':'child_process.spawnSync','kind':'report_header'},{'api':'child_process.exec','kind':'network_drive_discovery'}]))

    def test_no_discovery_on_another_platform_is_valid(self):
        self.assertTrue(validate_compiler_denials([],[]))

    def test_network_denial_cannot_be_disguised_as_discovery(self):
        self.assertFalse(validate_compiler_denials([{'api':'fetch','action':'blocked'}],[{'api':'fetch','kind':'report_header'}]))

    def test_unknown_child_process_remains_failure(self):
        self.assertFalse(validate_compiler_denials([{'api':'child_process.exec','action':'blocked'}],[{'api':'child_process.exec','kind':'other'}]))

    def test_allowed_or_forged_action_is_not_a_denied_probe(self):
        self.assertFalse(validate_compiler_denials([{'api':'child_process.exec','action':'allowed'}],[{'api':'child_process.exec','kind':'network_drive_discovery'}]))

    def test_duplicate_probes_and_extra_registry_records_fail(self):
        self.assertFalse(validate_compiler_denials([{'api':'child_process.exec','action':'blocked'}]*2,[{'api':'child_process.exec','kind':'network_drive_discovery'}]*2))
        self.assertFalse(validate_compiler_denials([],[{'api':'child_process.exec','kind':'network_drive_discovery'}]))

    def test_unclassified_denial_and_order_mismatch_fail(self):
        self.assertFalse(validate_compiler_denials([{'api':'child_process.exec','action':'blocked'}],[]))
        self.assertFalse(validate_compiler_denials([{'api':'child_process.exec','action':'blocked'}],[{'api':'child_process.spawnSync','kind':'report_header'}]))


if __name__=='__main__':unittest.main()
