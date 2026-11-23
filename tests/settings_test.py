import os
import tempfile

os.environ["DEBUG"] = "1"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="schwarmstack-test-")

from schwarmstack.settings import *  # noqa: E402,F403
