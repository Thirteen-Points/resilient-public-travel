"""Isolated real backend with explicit simulated demand for queue/ETA regression."""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['AI_ENABLED'] = 'false'
os.environ['OFFLINE_MODE'] = 'true'
demand_path = Path(sys.argv[2])
runtime_dir = ROOT / '.cache/queue-runtime'
runtime_dir.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(dir=runtime_dir) as directory:
    os.environ['FARE_DB_PATH'] = str(Path(directory) / 'fares.sqlite3')
    from backend.app.main import create_app, runtime
    from backend.app.engine.sim_adapter import CSimAdapter, MappingDemandAdapter, SimLoadProvider
    import uvicorn

    class TestLoadProvider(SimLoadProvider):
        def __call__(self, route, parameters):
            self.demand.default = float(demand_path.read_text(encoding='utf-8'))
            return super().__call__(route, parameters)

    demand = MappingDemandAdapter({}, source='browser_queue_simulation', provenance='simulated',
                                  freshness_s=0, default_rate_per_hour=0)
    runtime.engine.load_provider = TestLoadProvider(CSimAdapter(), demand)
    app = create_app(db_path=Path(directory) / 'events.sqlite3', review_token='queue-isolated-test')
    uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='warning')
