"""Generate initial administrator credentials without printing secrets or committing them."""
import argparse
import json
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.admin.store import password_hash

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--username",default="admin")
    parser.add_argument("--output",default="runs/admin-credentials.local")
    parser.add_argument("--env-output",default=".cache/admin-env.local")
    args=parser.parse_args()
    output,env_output=Path(args.output),Path(args.env_output)
    if output.exists() or env_output.exists():
        parser.error("Credential files already exist. Keep the existing encryption key; do not regenerate it on redeploy.")
    password=secrets.token_urlsafe(24)
    output.parent.mkdir(parents=True,exist_ok=True);env_output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({"url":"https://resilient-public-travel-api.onrender.com/admin/","username":args.username,"password":password},indent=2),encoding="utf-8")
    env_output.write_text(json.dumps({"ADMIN_USERNAME":args.username,"ADMIN_PASSWORD_HASH":password_hash(password),"ADMIN_ENCRYPTION_KEY":secrets.token_urlsafe(32)},indent=2),encoding="utf-8")
    print(f"Login credentials saved to {output.resolve()}")
    print(f"Render environment values saved to {env_output.resolve()}; keep this encryption key stable.")
if __name__=="__main__":main()
