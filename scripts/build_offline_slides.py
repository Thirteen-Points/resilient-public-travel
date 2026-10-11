"""Create a PDF backup from current public-page captures and frozen API replies.

Requires ReportLab during preparation; no PDF library is needed at demo launch.
The API tables are data evidence, not screenshots of a public Simulation page.
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
W, H = 960, 540


def load_evidence():
    directory = ROOT / ".cache/p4-browser"
    evidence = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if not evidence.get("passed"):
        raise ValueError("Create backup slides only from passed local evidence")
    scenarios = []
    for index, summary in enumerate(evidence["scenarios"]):
        result = json.loads((directory / f"scenario-{index}.json").read_text(encoding="utf-8"))
        if result["scenario_id"] != summary["scenario_id"]:
            raise ValueError("Scenario capture identity differs from the browser evidence")
        frozen = json.loads((ROOT / "data/sim" / f"{result['scenario_id']}.json").read_text(encoding="utf-8"))
        if result != frozen:
            raise ValueError("Captured API response differs from the current frozen scenario")
        scenarios.append(result)
    if len(scenarios) != 3:
        raise ValueError("Expected the three captured offline API scenarios")
    for name in ("01-offline-routes.png", "02-offline-sources.png"):
        if not (directory / name).is_file():
            raise ValueError(f"Missing current public-page capture: {name}")
    return evidence, scenarios


def value(number):
    if number is None:
        return "not supplied"
    return f"{number:,}" if isinstance(number, (int, float)) else str(number)


def main():
    evidence, scenarios = load_evidence()
    legacy, normal, stress = scenarios
    out = ROOT / "deploy/offline/media/slides.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(out), pagesize=(W, H))
    pdf.setTitle("ResilientRoute - public offline tour and frozen API evidence")
    pdf.setAuthor("ResilientRoute C - local simulated evidence")

    def text(lines, x=42, y=398, width=876, size=11, leading=18):
        pdf.setFillColor(HexColor("#C3D4DD")); pdf.setFont("Helvetica", size)
        for paragraph in lines:
            line = ""
            for word in str(paragraph).split():
                candidate = f"{line} {word}".strip()
                if line and stringWidth(candidate, "Helvetica", size) > width:
                    pdf.drawString(x, y, line); y -= leading; line = ""
                while stringWidth(word, "Helvetica", size) > width:
                    split = 1
                    while split < len(word) and stringWidth(word[:split + 1], "Helvetica", size) <= width:
                        split += 1
                    pdf.drawString(x, y, word[:split]); y -= leading; word = word[split:]
                line = f"{line} {word}".strip()
            pdf.drawString(x, y, line); y -= leading
        return y

    def frame(number, title, subtitle):
        pdf.setFillColor(HexColor("#0B1720")); pdf.rect(0, 0, W, H, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#40D8AF")); pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(42, H - 36, "RESILIENTROUTE / P4 C")
        pdf.setFillColor(HexColor("#FFFFFF")); pdf.setFont("Helvetica-Bold", 28)
        pdf.drawString(42, H - 78, title)
        text([subtitle], y=H - 103, size=11)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, 22, "LOCAL EVIDENCE | Public UI captures + frozen simulated API data | Team pitch sign-off pending")
        pdf.drawRightString(W - 42, 22, f"{number} / 6")

    def image(name, width=620):
        reader = ImageReader(str(ROOT / ".cache/p4-browser" / name))
        iw, ih = reader.getSize(); scale = min(width / iw, 344 / ih)
        pdf.drawImage(reader, 42, 66, iw * scale, ih * scale)

    def api_table(result, x=42, width=876, y=398):
        # Missing legacy fields remain missing; do not infer counts from rates.
        rows = [("Total delay", "total_delay_person_min"), ("Served demand", "served_demand"),
                ("Unmet demand", "unmet_demand"), ("Legacy capacity-gap field", "unstoppable_demand"),
                ("Unassigned demand", "unassigned_demand"), ("Overloaded shared segments", "overloaded_shared_resources")]
        text(["Metric / baseline / guided"], x=x, y=y, width=width, size=10)
        y -= 26
        for label, key in rows:
            unit = result.get("metric_units", {}).get(key, "unit metadata not supplied")
            text([f"{label}: {value(result['baseline'].get(key))} / {value(result['guided'].get(key))}", unit], x=x, y=y, width=width, size=10, leading=15)
            y -= 40
        reduction = result.get("delta", {}).get("delay_reduction_pct")
        interpretation = "Guided delay is higher." if reduction is not None and reduction < 0 else "No delay improvement." if reduction == 0 else "Positive simulated delay reduction." if reduction is not None else "Benefit metadata not supplied."
        text([f"Delay reduction: {value(reduction)}%", interpretation], x=x, y=y, width=width, size=10)
        return y - 44

    frame(1, "Five minutes: public pages and API evidence", "Current tour: routes for the first minute; How it works stays visible for the remaining four minutes.")
    text([f"Population: {value(normal.get('population'))} simulated people",
          f"Directed OD pairs: {value(normal.get('od_count'))}; shared resources: {value(normal.get('capacity_model', {}).get('shared_resource_count'))}",
          f"Seed: {value(normal.get('seed'))}; window: {value(normal.get('window_min'))} minutes",
          "0:00-1:00  Query the local API through the prepared public planner.",
          "1:00-2:00  Show offline source status; narrate the legacy API result.",
          "2:00-3:00  Keep How it works visible; narrate the normal frozen API result.",
          "3:00-4:00  Explain stress API metrics and their simulated capacity sensitivity.",
          "4:00-5:00  Explain source/path limits and assumptions from the captured JSON.",
          "API tables below are frozen response evidence. No public Simulation UI is shown."], y=387, leading=27)
    pdf.showPage()
    frame(2, "0:00-1:00 - Query a modelled journey", "Actual public route-page capture from the isolated production frontend and local API.")
    image("01-offline-routes.png")
    text(["Actual public-page screenshot", "Browser WAN requests blocked", "Local API remains reachable", "Source status and path limits remain available", "No hosted timing claim"], x=688, width=225)
    pdf.showPage()
    frame(3, "1:00-5:00 - Sources and model boundaries", "Actual How it works capture; the presenter narrates API data without claiming a Simulation screen.")
    image("02-offline-sources.png")
    text(["Actual public-page screenshot", "External collection is offline", "Path sources remain inspectable", "Unverified connections stay schematic", "API results: scenario-0/1/2.json", "The JSON retains all frozen assumptions"], x=688, width=225)
    pdf.showPage()
    frame(4, "Legacy scenario - frozen API evidence", legacy["scenario_id"] + " | Data table, not a UI screenshot.")
    y = api_table(legacy)
    text([f"Provenance: {legacy.get('provenance', 'not supplied')}; generated: {legacy.get('generated_at', 'not supplied')}", "Current capture equals the checked-in scenario JSON. Legacy missing fields remain explicitly unavailable."], y=y, size=10)
    pdf.showPage()
    frame(5, "Normal and stress - frozen API evidence", "Values, units and timestamps are read from the captured current responses, verified against data/sim.")
    for x, title, result in ((42, "Normal", normal), (504, "Stress", stress)):
        text([title], x=x, width=414, y=402, size=13)
        y = api_table(result, x=x, width=414, y=374)
        text([f"Generated: {result.get('generated_at', 'not supplied')}", f"Route query: {result.get('query_time', 'not supplied')}"], x=x, width=414, y=y, size=9, leading=14)
    pdf.showPage()
    frame(6, "4:00-5:00 - State the evidence boundaries", "Selected assumptions below come from the current P3 API JSON; full assumptions stay in each scenario file.")
    selected = list(normal.get("assumptions", [])[-2:]) + list(stress.get("assumptions", [])[-1:])
    y = text(selected, y=392, size=11, leading=19)
    text(["Fallback media and screenshots establish a local technical record, not a live production demonstration.",
          "The checked-in PR #110 video/PDF are historical backups. Regenerate only after accepting new public-page/API evidence.",
          "Build SHA: " + evidence["frontend_build"]["commit_sha"]], y=y - 26, size=10, leading=18)
    pdf.showPage(); pdf.save()
    print(out.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
