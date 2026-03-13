import pytest

from deploy.utils.config import parse_instance_name

# ---------------------------------------------------------------------------
# Valid names from the SPEC examples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        # (prefix, slug, environment, suffix)
        ("odoo-myproject-production", ("odoo", "myproject", "production", None)),
        ("odoo-myproject-staging-02", ("odoo", "myproject", "staging", "02")),
        ("odoo-my-cool-project-production", ("odoo", "my-cool-project", "production", None)),
        ("openerp-legacy-integration", ("openerp", "legacy", "integration", None)),
        ("service-myapi-production-eu", ("service", "myapi", "production", "eu")),
        ("service-worker-staging", ("service", "worker", "staging", None)),
    ],
)
def test_spec_examples(name, expected):
    assert parse_instance_name(name) == expected


# ---------------------------------------------------------------------------
# All known environment values are recognised
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env",
    ["integration", "staging", "production", "hotfix", "debug", "demo"],
)
def test_all_known_environments(env):
    _, _, environment, suffix = parse_instance_name(f"odoo-proj-{env}")
    assert environment == env
    assert suffix is None


# ---------------------------------------------------------------------------
# Suffix detection
# ---------------------------------------------------------------------------


def test_suffix_is_captured():
    _, _, _, suffix = parse_instance_name("odoo-proj-production-vn")
    assert suffix == "vn"


def test_no_suffix_when_last_segment_is_env():
    _, _, environment, suffix = parse_instance_name("odoo-proj-staging")
    assert environment == "staging"
    assert suffix is None


def test_suffix_does_not_leak_into_slug():
    _, slug, environment, suffix = parse_instance_name("odoo-my-proj-staging-eu")
    assert slug == "my-proj"
    assert environment == "staging"
    assert suffix == "eu"


# ---------------------------------------------------------------------------
# Prefix and slug extraction
# ---------------------------------------------------------------------------


def test_prefix_is_first_segment():
    prefix, _, _, _ = parse_instance_name("openerp-legacy-production")
    assert prefix == "openerp"


def test_slug_joins_middle_segments_with_hyphen():
    _, slug, _, _ = parse_instance_name("odoo-my-cool-project-production")
    assert slug == "my-cool-project"


def test_single_segment_slug():
    _, slug, _, _ = parse_instance_name("service-worker-staging")
    assert slug == "worker"


# ---------------------------------------------------------------------------
# Invalid names raise ValueError
# ---------------------------------------------------------------------------


def test_too_few_segments_raises():
    with pytest.raises(ValueError):
        parse_instance_name("odoo-production")  # no slug


def test_no_hyphens_raises():
    with pytest.raises(ValueError):
        parse_instance_name("justoneword")


def test_unknown_environment_raises():
    with pytest.raises(ValueError, match="Cannot determine environment"):
        parse_instance_name("odoo-proj-unknown")


def test_error_message_lists_known_envs():
    with pytest.raises(ValueError, match="production"):
        parse_instance_name("odoo-proj-badenv")
