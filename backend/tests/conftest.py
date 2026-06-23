import os

os.environ["API_PREFIX"] = ""
os.environ["GITHUB_CLIENT_ID"] = ""
os.environ["GITHUB_CLIENT_SECRET"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""


def pytest_collection_modifyitems(config, items):
    """Auto-tag tests with a category marker based on file path.

    Mirrors the logic in the root conftest.py. The root conftest only
    applies when running from the project root; this one covers the
    case where pytest is invoked from inside backend/.
    """
    root = str(config.rootdir)
    backend_root = os.path.normpath(os.path.join(root, "tests"))
    sdk_root = os.path.normpath(os.path.join(root, "..", "agent-sdk", "tests"))
    games_root = os.path.normpath(os.path.join(root, "..", "games"))

    for item in items:
        path = os.path.normpath(str(item.fspath))
        if path.startswith(backend_root):
            item.add_marker("backend")
        elif path.startswith(sdk_root):
            item.add_marker("sdk")
        elif path.startswith(games_root):
            item.add_marker("games")
            item.add_marker("backend")
