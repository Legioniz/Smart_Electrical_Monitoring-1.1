from scripts.verify_project_paths import verify


def test_project_paths_and_browser_assets_resolve():
    errors = verify()
    assert not errors, "Project path verification failed:\n" + "\n".join(errors)
