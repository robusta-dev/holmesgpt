import os

from holmes.plugins.runbooks import (
    get_runbook_by_path,
    load_runbook_catalog,
    DEFAULT_RUNBOOK_SEARCH_PATH,
)


def test_load_runbook_catalog():
    runbooks = load_runbook_catalog()
    assert runbooks is not None
    assert len(runbooks.catalog) > 0
    for runbook in runbooks.catalog:
        assert runbook.description is not None
        assert runbook.link is not None
        runbook_link = get_runbook_by_path(runbook.link, [DEFAULT_RUNBOOK_SEARCH_PATH])
        # assert file path exists
        assert os.path.exists(
            runbook_link
        ), f"Runbook link {runbook.link} does not exist at {runbook_link}"
