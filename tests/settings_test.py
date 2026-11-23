import os
import tempfile

os.environ["DEBUG"] = "1"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="schwarmstack-test-")
# Tests laufen standardmäßig gegen die lokale Platte; S3-Tests stellen gezielt um.
os.environ["STORAGE_BACKEND"] = "local"

from schwarmstack.settings import *  # noqa: E402,F403
