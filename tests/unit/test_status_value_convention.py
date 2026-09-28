"""Every status a node sets is the plain string, never the bare enum member.

`AgentStatus` is a str enum, so a bare member compares equal and slips through equality
checks; the convention is enforced here structurally instead.
"""

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"


def _bare_members():
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "AgentStatus"
                and not (isinstance(parents.get(node), ast.Attribute) and parents[node].attr == "value")
            ):
                yield f"{path.relative_to(_SRC.parent)}:{node.lineno} AgentStatus.{node.attr}"


def test_no_bare_agent_status_member_in_src():
    assert list(_bare_members()) == []
