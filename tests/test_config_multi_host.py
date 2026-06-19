from __future__ import annotations

import pytest

from trobz_deploy.utils.config import normalize_hosts, resolve_host_steps

# ---------------------------------------------------------------------------
# normalize_hosts
# ---------------------------------------------------------------------------


def test_none_host_becomes_single_entry():
    assert normalize_hosts(None) == [{"host": None, "watch": None, "steps": {}}]


def test_single_string_host_is_untouched_by_ssh_user():
    # ssh_user only applies to list entries; a plain string keeps any embedded user as-is.
    assert normalize_hosts("deploy@myserver.example.com", ssh_user="openerp") == [
        {"host": "deploy@myserver.example.com", "watch": None, "steps": {}}
    ]


def test_list_of_bare_strings_has_no_overrides():
    assert normalize_hosts(["host1.example.com", "host2.example.com"]) == [
        {"host": "host1.example.com", "watch": None, "steps": {}},
        {"host": "host2.example.com", "watch": None, "steps": {}},
    ]


def test_list_entry_with_overrides_extracts_watch_and_steps():
    raw = [
        {
            "host2.example.com": {
                "watch": True,
                "steps": {"update": "pull, venv, db"},
            }
        },
        {"host1.example.com": {"watch": True, "steps": {"update": "pull, venv"}}},
    ]

    result = normalize_hosts(raw)

    assert result == [
        {"host": "host2.example.com", "watch": True, "steps": {"update": "pull, venv, db"}},
        {"host": "host1.example.com", "watch": True, "steps": {"update": "pull, venv"}},
    ]


def test_list_entry_with_null_overrides_is_equivalent_to_bare_string():
    assert normalize_hosts([{"host1.example.com": None}]) == [{"host": "host1.example.com", "watch": None, "steps": {}}]


def test_ssh_user_prefixes_bare_hostnames_in_list_form():
    result = normalize_hosts(["host1.example.com"], ssh_user="openerp")

    assert result == [{"host": "openerp@host1.example.com", "watch": None, "steps": {}}]


def test_ssh_user_does_not_override_embedded_user():
    result = normalize_hosts(["deploy@host1.example.com"], ssh_user="openerp")

    assert result == [{"host": "deploy@host1.example.com", "watch": None, "steps": {}}]


def test_ssh_user_does_not_apply_to_localhost():
    result = normalize_hosts(["localhost"], ssh_user="openerp")

    assert result == [{"host": "localhost", "watch": None, "steps": {}}]


def test_invalid_list_entry_type_raises():
    with pytest.raises(ValueError, match="Invalid ssh_host list entry"):
        normalize_hosts([123])


def test_multi_key_mapping_entry_raises():
    with pytest.raises(ValueError, match="Invalid ssh_host list entry"):
        normalize_hosts([{"host1.example.com": {}, "host2.example.com": {}}])


def test_non_mapping_overrides_raises():
    with pytest.raises(ValueError, match="Invalid ssh_host overrides"):
        normalize_hosts([{"host1.example.com": "not-a-mapping"}])


# ---------------------------------------------------------------------------
# resolve_host_steps
# ---------------------------------------------------------------------------

STEPS = {"pull": "Pull", "venv": "Venv", "db": "DB"}


def test_no_host_override_keeps_cli_resolved_steps():
    steps, skip = resolve_host_steps({}, "update", ["all"], [], STEPS)

    assert steps == ["all"]
    assert skip == []


def test_host_override_applies_when_cli_did_not_constrain():
    steps, skip = resolve_host_steps({"update": "pull, venv"}, "update", ["all"], [], STEPS)

    assert steps == ["pull", "venv"]
    assert skip == []


def test_host_override_for_other_action_is_ignored():
    steps, skip = resolve_host_steps({"configure": "dir"}, "update", ["all"], [], STEPS)

    assert steps == ["all"]
    assert skip == []


def test_cli_steps_override_wins_over_host_override():
    steps, skip = resolve_host_steps({"update": "pull, venv"}, "update", ["db"], [], STEPS)

    assert steps == ["db"]
    assert skip == []


def test_cli_except_override_wins_over_host_override():
    steps, skip = resolve_host_steps({"update": "pull, venv"}, "update", ["all"], ["db"], STEPS)

    assert steps == ["all"]
    assert skip == ["db"]


def test_invalid_host_step_slug_raises():
    with pytest.raises(ValueError, match="Invalid ssh_host steps\\.update"):
        resolve_host_steps({"update": "bogus"}, "update", ["all"], [], STEPS)
