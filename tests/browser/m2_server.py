"""Isolated browser-regression server; never touches the user's event database."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ['AI_ENABLED'] = 'false'
os.environ['OFFLINE_MODE'] = 'true'
from backend.app.admin.store import password_hash

# These credentials exist only in the isolated temporary test application.
os.environ['ADMIN_USERNAME'] = 'operator'
os.environ['ADMIN_PASSWORD_HASH'] = password_hash('local-test-password')
os.environ['ADMIN_ENCRYPTION_KEY'] = 'isolated-browser-test-encryption-key-2026'
os.environ['ADMIN_COOKIE_SECURE'] = 'false'
os.environ['RENDER_EXTERNAL_URL'] = f'http://127.0.0.1:{sys.argv[1]}'
with tempfile.TemporaryDirectory() as directory:
    # Importing main also creates its ASGI app; isolate that database too.
    os.environ['DB_PATH'] = str(Path(directory) / 'events.sqlite3')
    from backend.app.main import create_app
    import uvicorn

    app = create_app(db_path=Path(directory) / 'events.sqlite3', review_token='m2-isolated-test')
    uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='warning')
