import unittest

from factory.engineering_pod import ImplementationWorkPackage, WorkspaceAllocator, WorkspaceAssignment


def package(*, mission_id="MISSION-42", package_id="PKG-FE", scopes=("app/frontend",)):
    return ImplementationWorkPackage(
        package_id=package_id,
        mission_id=mission_id,
        owner_agent="A05-FRONTEND",
        discipline="FRONTEND",
        objective="Implement client",
        requirement_ids=("REQ-1",),
        depends_on=(),
        write_scopes=scopes,
        expected_artifacts=("frontend-build",),
        verification_methods=("unit test",),
    )


class WorkspaceAssignmentTests(unittest.TestCase):
    def test_allocator_is_deterministic_and_scope_exact(self):
        item = package(mission_id="Mission Fancy", package_id="PKG UI")
        allocator = WorkspaceAllocator()
        first = allocator.allocate(item)
        second = allocator.allocate(item)
        self.assertEqual(first, second)
        self.assertEqual(first.workspace_id, "Mission Fancy:PKG UI")
        self.assertEqual(first.branch_name, "factory/mission-fancy/pkg-ui")
        self.assertEqual(first.write_scopes, item.write_scopes)

    def test_assignment_cannot_widen_validated_scope(self):
        item = package()
        assignment = WorkspaceAssignment(
            workspace_id="MISSION-42:PKG-FE",
            mission_id=item.mission_id,
            package_id=item.package_id,
            owner_agent=item.owner_agent,
            branch_name="factory/mission-42/pkg-fe",
            write_scopes=("app",),
        )
        with self.assertRaisesRegex(ValueError, "scopes must match"):
            assignment.validate_for(item)

    def test_assignment_cannot_change_owner(self):
        item = package()
        assignment = WorkspaceAssignment(
            workspace_id="MISSION-42:PKG-FE",
            mission_id=item.mission_id,
            package_id=item.package_id,
            owner_agent="A06-BACKEND",
            branch_name="factory/mission-42/pkg-fe",
            write_scopes=item.write_scopes,
        )
        with self.assertRaisesRegex(ValueError, "owner_agent mismatch"):
            assignment.validate_for(item)

    def test_assignment_cannot_alias_another_canonical_identity(self):
        item = package()
        assignment = WorkspaceAssignment(
            workspace_id="mission-42:pkg-fe",
            mission_id=item.mission_id,
            package_id=item.package_id,
            owner_agent=item.owner_agent,
            branch_name="factory/mission-42/pkg-fe",
            write_scopes=item.write_scopes,
        )
        with self.assertRaisesRegex(ValueError, "preserve canonical"):
            assignment.validate_for(item)


if __name__ == "__main__":
    unittest.main()
