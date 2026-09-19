"""
run_api.py  —  headless launcher for the flybrain-connectome HTTP API.
Used by start_api_autostart.bat for boot-time auto-start (schtasks /onstart).

It sets FLYBRAIN_DATA_DIR (default: ../male_cns relative to this file) and logs
to api_runtime.log so a crashed service is diagnosable without a console.
"""
import os
import sys
import logging
from pathlib import Path

HERE = Path(__file__).resolve().parent
# default data dir = ../male_cns (i.e. C:\Users\xing\Desktop\flybrain-connectome\male_cns)
os.environ.setdefault("FLYBRAIN_DATA_DIR", str(HERE.parent / "male_cns"))

logging.basicConfig(
    filename=str(HERE / "api_runtime.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.info("flybrain api bootstrap: FLYBRAIN_DATA_DIR=%s python=%s",
             os.environ["FLYBRAIN_DATA_DIR"], sys.executable)

try:
    sys.path.insert(0, str(HERE))
    from mcp_connectome import api_server
    api_server.main()
except Exception:
    logging.exception("flybrain api crashed")
