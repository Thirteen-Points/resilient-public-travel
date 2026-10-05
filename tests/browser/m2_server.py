"""Isolated browser-regression server; never touches the user's event database."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['AI_ENABLED'] = 'false'
os.environ['OFFLINE_MODE'] = 'true'
from backend.app.main import create_app
import uvicorn

runtime = ROOT / '.cache/browser-runtime'
runtime.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=runtime) as directory:
    app = create_app(db_path=Path(directory) / 'events.sqlite3', review_token='m2-isolated-test')
    uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='warning')
