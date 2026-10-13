"""English UI copy stays English while submitted evidence remains verbatim."""
import re
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app.main import create_app


def test_offline_public_system_copy_and_original_report():
    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(db_path=Path(directory) / 'copy.sqlite3', review_token='copy-test')) as client:
            journey = {'origin': 'TAW', 'destination': 'ADM', 'depart_at': '2026-10-15T08:20:00+08:00'}
            routes = client.post('/api/routes/query', json={**journey, 'profile': {'preset': 'fastest'}})
            assert routes.status_code == 200
            assert routes.json()
            strings = [text for route in routes.json() for text in [route['label'], route['explain'], *route['warnings'], *route['notes']]]
            preference = client.post('/api/persona/parse', json={'free_text': 'wheelchair, please keep costs low'})
            assert preference.status_code == 200
            strings.append(preference.json()['explanation'])
            chat = client.post('/api/ai/chat', json={**journey, 'message': 'Please show routes.'})
            assert chat.status_code == 200
            strings.append(chat.json()['message'])
            assert all(not re.search(r'[\u3400-\u9fff]', text) for text in strings), strings

            original = '红磡站有乘客等候，情况尚未确认。'
            receipt = client.post('/api/signals', json={'raw_text': original, 'lang': 'zh-HK'})
            assert receipt.status_code == 202
            report = client.get('/api/signals/' + receipt.json()['signal_id'], headers={'X-Review-Token': 'copy-test'}).json()
            assert report['raw_text'] == original
            assert report['source_name'] == 'ResilientRoute user report (unverified)'
