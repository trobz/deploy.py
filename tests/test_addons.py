from unittest.mock import MagicMock

from trobz_deploy.utils.addons import get_addons_path


def test_get_addons_path_passes_codebase_explicitly():
    """odoo-addons-path does not detect the CWD implicitly: the instance path
    must be given as the codebase argument."""
    executor = MagicMock()
    executor.capture.return_value = "/srv/odoo/addons"

    assert get_addons_path(executor, "/home/deploy/my instance") == "/srv/odoo/addons"
    executor.capture.assert_called_once_with(
        "odoo-addons-path '/home/deploy/my instance'", cwd="/home/deploy/my instance"
    )
