import os

os.environ["API_PREFIX"] = ""
for _var in ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
    os.environ.setdefault(_var, "")
