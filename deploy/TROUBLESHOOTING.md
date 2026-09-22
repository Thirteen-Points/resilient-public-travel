# Troubleshooting - ResilientRoute

> Common issues and how to fix them.

---

## 1. Server won't start

### "ModuleNotFoundError: No module named 'fastapi'"
**Cause**: Dependencies not installed.
**Fix**: 
```bash
pip install -r backend/requirements.txt
```
Or re-run the startup script which handles this automatically.

### "Address already in use" / Port 8000 taken
**Cause**: Another process is using port 8000.
**Fix**: 
```bash
# Use a different port
PORT=9000 ./scripts/start.sh
# Or kill the process using port 8000:
# Linux: lsof -i :8000 && kill <PID>
# Windows: netstat -ano | findstr :8000
```

### "Python not found"
**Cause**: Python not installed or not in PATH.
**Fix**: Install Python 3.11+ from https://python.org

---

## 2. Data validation failures

### "FAIL: stations.json"
**Cause**: Data file is missing or corrupted.
**Fix**: 
```bash
git checkout data/network/stations.json
python scripts/validate_data.py
```

### "Coordinate out of HK range"
**Cause**: A coordinate was entered incorrectly (wrong lat/lng or swapped order).
**Fix**: Check the data file. Hong Kong coordinates are approximately:
- Latitude: 22.0 to 23.0
- Longitude: 113.5 to 114.5
- Lat comes first, lng second

---

## 3. Health check returns "degraded"

### "data_files._all_present: false"
**Cause**: One or more critical data files are missing.
**Fix**: 
```bash
python scripts/validate_data.py
# Check which files are missing
git status
git checkout -- data/ contracts/seed/
```

### "data_files._all_loadable: false"
**Cause**: A JSON file exists but has syntax errors.
**Fix**: 
```bash
python -c "import json; json.load(open('data/network/stations.json'))"
# Fix the JSON syntax error
```

---

## 4. LLM-related issues

### "LLM enabled but no API key"
**Cause**: `LLM_ENABLED=true` but `LLM_API_KEY` is empty.
**Fix**: Either set the API key in `.env` or disable LLM:
```bash
LLM_ENABLED=false  # in .env
```
**Note**: The system works fine without LLM. Route queries use deterministic logic.

### "LLM call timeout"
**Cause**: The LLM API is slow or unreachable.
**Fix**: The system automatically falls back to rule-based extraction. No action needed.
For persistent issues, set `LLM_ENABLED=false`.

---

## 5. Docker issues

### "docker-compose: command not found"
**Cause**: Docker Compose not installed.
**Fix**: Install Docker Desktop (includes Compose).

### Container exits immediately
**Cause**: Missing data files or Python errors.
**Fix**: 
```bash
docker-compose -f deploy/docker-compose.yml logs
# Check the error message
```

---

## 6. Offline mode issues

### "No external data in offline mode"
**This is expected.** In offline mode, all data comes from local JSON files. 
The system is designed to work fully offline. See `deploy/offline/README.md`.

### "SimResult numbers are placeholders"
**This is expected.** The `sim.seed.json` file contains placeholder numbers.
C-Sim will replace them with real simulation results. The structure and provenance 
labels are correct.

---

## 7. Common development issues

### "Changes not reflected after edit"
**Cause**: Python bytecode cache or uvicorn not reloading.
**Fix**: 
```bash
# Clear __pycache__
find . -type d -name __pycache__ -exec rm -rf {} +
# Restart with --reload
python -m uvicorn backend.app.main:app --reload
```

### "CORS error in browser"
**Cause**: Frontend running on a different port than backend.
**Fix**: The backend allows all origins in dev mode. If still failing, check:
- Backend is running on the expected port
- Network/firewall not blocking the port

---

## 8. Getting help

1. Check `data/PROVENANCE.md` for data source questions
2. Check `data/DATA_QUALITY.md` for data quality issues
3. Check `deploy/DEPLOYMENT.md` for deployment questions
4. Run `python scripts/preflight.py` for a full diagnostic
5. Run `python scripts/validate_data.py` for data validation
6. Run `python -m pytest tests/ -v` for all tests
