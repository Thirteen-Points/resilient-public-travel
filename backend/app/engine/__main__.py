"""Run: python -m backend.app.engine --events contracts/seed/event.seed.json"""
import argparse
import json
import sys

from .service import RouteEngine

from pathlib import Path

fixture = json.loads((Path(__file__).parent / 'fixtures/seed_policy.json').read_text(encoding='utf-8'))['query']
parser = argparse.ArgumentParser()
parser.add_argument("--origin", default=fixture["origin"])
parser.add_argument("--destination", default=fixture["destination"])
parser.add_argument("--depart-at", default=fixture["depart_at"])
parser.add_argument("--events")
parser.add_argument("--mobility", choices=["standard", "reduced", "wheelchair"], default="standard")
args = parser.parse_args()
sys.stdout.reconfigure(encoding="utf-8")
engine = RouteEngine.from_seed(events_path=args.events)
print(json.dumps(engine.query_details(args.origin, args.destination, args.depart_at,
                                     {"mobility": args.mobility}), ensure_ascii=False, indent=2))
