import logging
from unittest.mock import MagicMock

import pandas as pd

from testbench_requirement_service.readers.excel.utils import (
    _create_placeholder_node,
    build_requirement_tree_from_dataframe,
)


def make_config(folder_pattern: str = ".*folder.*") -> MagicMock:
    """Return a minimal config mock satisfying build_requirementobjectnode_from_row_data."""
    cfg = MagicMock()
    cfg.requirement_folderPattern = folder_pattern
    return cfg


def make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a DataFrame from rows; missing keys default to empty string."""
    columns = ["id", "version", "name", "hierarchyID"]
    return pd.DataFrame([{col: row.get(col, "") for col in columns} for row in rows])


def find_node(nodes, key_id):
    """Recursively find a node by key.id in the given list."""
    for n in nodes:
        if n.key.id == key_id:
            return n
        if n.children:
            result = find_node(n.children, key_id)
            if result:
                return result
    return None


class TestCreatePlaceholderNode:
    def test_id_format(self):
        node = _create_placeholder_node("1.1.2")
        assert node.key.id == "__placeholder__1.1.2"

    def test_version(self):
        node = _create_placeholder_node("1.1.2")
        assert node.key.version == "placeholder"

    def test_name(self):
        node = _create_placeholder_node("1.1.2")
        assert node.name == "[1.1.2]"

    def test_not_requirement(self):
        node = _create_placeholder_node("1.1.2")
        assert node.requirement is False

    def test_no_children(self):
        node = _create_placeholder_node("1.1.2")
        assert node.children is None

    def test_extended_id_matches_key_id(self):
        node = _create_placeholder_node("2.3")
        assert node.extendedID == node.key.id


class TestBuildTreeNormal:
    def test_flat_list_without_hierarchy_column(self):
        """When there is no hierarchyID column the result is a flat list in original order."""
        df = pd.DataFrame(
            [
                {"id": "A", "version": "1", "name": "Alpha"},
                {"id": "B", "version": "1", "name": "Beta"},
            ]
        )
        tree = build_requirement_tree_from_dataframe(df, make_config())

        assert [n.key.id for n in tree] == ["A", "B"]
        assert all(n.children is None for n in tree)

    def test_two_level_tree(self):
        """Standard 2-level tree: 1 → [1.1, 1.2]."""
        rows = [
            {"id": "R1", "version": "1", "name": "Root", "hierarchyID": "1"},
            {"id": "R11", "version": "1", "name": "Child1", "hierarchyID": "1.1"},
            {"id": "R12", "version": "1", "name": "Child2", "hierarchyID": "1.2"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        assert len(tree) == 1
        root = tree[0]
        assert root.key.id == "R1"
        assert len(root.children) == 2
        assert {c.key.id for c in root.children} == {"R11", "R12"}

    def test_three_level_tree(self):
        rows = [
            {"id": "R1", "version": "1", "name": "L1", "hierarchyID": "1"},
            {"id": "R11", "version": "1", "name": "L2", "hierarchyID": "1.1"},
            {"id": "R111", "version": "1", "name": "L3", "hierarchyID": "1.1.1"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        assert tree[0].children[0].children[0].key.id == "R111"


class TestBuildTreeMissingParents:
    def test_single_missing_parent_creates_placeholder_node(self):
        """1.1.2 is absent; 1.1.2.1 must be attached under a new placeholder node for 1.1.2."""
        rows = [
            {"id": "R1", "version": "1", "name": "L1", "hierarchyID": "1"},
            {"id": "R11", "version": "1", "name": "L2", "hierarchyID": "1.1"},
            # 1.1.2 intentionally absent
            {"id": "R1121", "version": "1", "name": "L4", "hierarchyID": "1.1.2.1"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        assert len(tree) == 1
        r1 = tree[0]
        assert r1.key.id == "R1"

        r11 = r1.children[0]
        assert r11.key.id == "R11"

        # R11 → placeholder 1.1.2
        assert len(r11.children) == 1
        placeholder = r11.children[0]
        assert placeholder.key.id == "__placeholder__1.1.2"
        assert placeholder.key.version == "placeholder"
        assert placeholder.name == "[1.1.2]"
        assert placeholder.requirement is False

        # placeholder 1.1.2 → real node
        assert len(placeholder.children) == 1
        assert placeholder.children[0].key.id == "R1121"

    def test_missing_parent_at_root_level(self):
        """Node '2' is absent; 2.1 must be under a placeholder root node for '2'."""
        rows = [
            {"id": "R1", "version": "1", "name": "L1", "hierarchyID": "1"},
            # hierarchy "2" is missing
            {"id": "R21", "version": "1", "name": "L2", "hierarchyID": "2.1"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        root_ids = [n.key.id for n in tree]
        assert "R1" in root_ids
        assert "__placeholder__2" in root_ids

        placeholder_2 = next(n for n in tree if n.key.id == "__placeholder__2")
        assert len(placeholder_2.children) == 1
        assert placeholder_2.children[0].key.id == "R21"

    def test_chain_of_two_missing_parents(self):
        """Both 1.1.2 and 1.1.2.3 are absent; 1.1.2.3.1 must sit 4 levels deep."""
        rows = [
            {"id": "R1", "version": "1", "name": "L1", "hierarchyID": "1"},
            {"id": "R11", "version": "1", "name": "L2", "hierarchyID": "1.1"},
            # 1.1.2 and 1.1.2.3 are both missing
            {"id": "R11231", "version": "1", "name": "L5", "hierarchyID": "1.1.2.3.1"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        assert len(tree) == 1
        r1 = tree[0]
        r11 = r1.children[0]
        assert r11.key.id == "R11"

        placeholder_112 = r11.children[0]
        assert placeholder_112.key.id == "__placeholder__1.1.2"

        placeholder_1123 = placeholder_112.children[0]
        assert placeholder_1123.key.id == "__placeholder__1.1.2.3"

        assert placeholder_1123.children[0].key.id == "R11231"

    def test_siblings_all_attach_to_same_placeholder_parent(self):
        """Multiple children of the same missing parent share one placeholder node."""
        rows = [
            # 1.1 and 1.1.2 are both missing
            {"id": "R1121", "version": "1", "name": "C1", "hierarchyID": "1.1.2.1"},
            {"id": "R1122", "version": "1", "name": "C2", "hierarchyID": "1.1.2.2"},
            {"id": "R1123", "version": "1", "name": "C3", "hierarchyID": "1.1.2.3"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        placeholder_112 = find_node(tree, "__placeholder__1.1.2")
        assert placeholder_112 is not None
        assert len(placeholder_112.children) == 3
        assert {c.key.id for c in placeholder_112.children} == {"R1121", "R1122", "R1123"}

    def test_only_one_placeholder_node_created_per_missing_hierarchy(self):
        """The same missing hierarchy ID must not produce duplicate placeholder nodes."""
        rows = [
            {"id": "R1121", "version": "1", "name": "C1", "hierarchyID": "1.1.2.1"},
            {"id": "R1122", "version": "1", "name": "C2", "hierarchyID": "1.1.2.2"},
        ]
        tree = build_requirement_tree_from_dataframe(make_df(rows), make_config())

        placeholder_112_nodes = []

        def collect(nodes):
            for n in nodes:
                if n.key.id == "__placeholder__1.1.2":
                    placeholder_112_nodes.append(n)
                if n.children:
                    collect(n.children)

        collect(tree)
        assert len(placeholder_112_nodes) == 1

    def test_warning_logged_for_each_missing_hierarchy(self, caplog):
        """A warning mentioning the missing hierarchyID is emitted for every gap."""
        rows = [
            {"id": "R121", "version": "1", "name": "L3", "hierarchyID": "1.2.1"},
        ]
        with caplog.at_level(logging.WARNING):
            build_requirement_tree_from_dataframe(make_df(rows), make_config())

        # Expect warnings for both '1.2' (direct parent) and '1' (grandparent)
        assert any("'1.2'" in r.getMessage() for r in caplog.records)
        assert any(r.getMessage().startswith("hierarchyID '1'") for r in caplog.records)
