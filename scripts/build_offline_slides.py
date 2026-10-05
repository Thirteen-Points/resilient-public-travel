"""Generate the C technical PDF backup from actual local screenshots/evidence.

Requires ReportLab during preparation; no PDF library is needed at demo launch.
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
W, H = 960, 540


def main():
    evidence = json.loads((ROOT / ".cache/p4-browser/result.json").read_text(encoding="utf-8"))
    performance = json.loads((ROOT / ".cache/p4-c/performance.json").read_text(encoding="utf-8"))
    if not evidence["passed"] or not performance["ok"]:
        raise ValueError("Create backup slides only from passed local evidence")
    out = ROOT / "deploy/offline/media/slides.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(out), pagesize=(W, H))
    pdf.setTitle("ResilientRoute - P4 C technical offline backup")
    pdf.setAuthor("ResilientRoute C - local simulated evidence")

    def frame(number, title, subtitle):
        pdf.setFillColor(HexColor("#0B1720")); pdf.rect(0, 0, W, H, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#40D8AF")); pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(42, H - 36, "RESILIENTROUTE / P4 C")
        pdf.setFillColor(HexColor("#FFFFFF")); pdf.setFont("Helvetica-Bold", 28)
        pdf.drawString(42, H - 78, title)
        pdf.setFillColor(HexColor("#C3D4DD")); pdf.setFont("Helvetica", 11)
        pdf.drawString(42, H - 103, subtitle)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, 22, "LOCAL SIMULATED EVIDENCE | C technical backup | Team final PPT sign-off pending")
        pdf.drawRightString(W - 42, 22, f"{number} / 6")

    def image(name, x=42, y=66, width=620, height=344):
        reader = ImageReader(str(ROOT / ".cache/p4-browser" / name))
        iw, ih = reader.getSize(); scale = min(width / iw, height / ih)
        pdf.drawImage(reader, x, y, iw * scale, ih * scale)

    def notes(lines, x=688, y=398):
        pdf.setFillColor(HexColor("#C3D4DD")); pdf.setFont("Helvetica", 11)
        for line in lines:
            pdf.drawString(x, y, line); y -= 21

    frame(1, "Five minutes, with an honest capacity gap", "Frozen inputs and real local UI. No scoring weights or presets changed.")
    pdf.setFillColor(HexColor("#40D8AF")); pdf.setFont("Helvetica-Bold", 44)
    pdf.drawString(42, 350, "10,000")
    pdf.setFillColor(HexColor("#FFFFFF")); pdf.setFont("Helvetica", 16)
    pdf.drawString(42, 319, "simulated people / 30 directed OD pairs / 44 shared resources")
    notes(["0:00 Routes - local API and prepared frontend", "1:00 Older M0 negative benefit - retain the result",
           "2:00 P3 normal - 0% delay reduction", "3:00 P3 stress - 10% invented capacity sensitivity",
           "4:00 Gap, units and assumptions"], 42, 268)
    notes(["Seed: 20260922", "Window: 60 minutes", "No live passenger loads", "No production timing claim"], 688, 350)
    pdf.showPage()
    frame(2, "0:00 - Query a modelled journey", "Tai Wai -> Admiralty / 2026-09-22 08:20 HKT / unchanged Commuter + Fastest")
    image("01-offline-routes.png")
    q = performance["query"]["loopback_http_sequential"]
    notes(["Actual local API response", "All browser WAN blocked", "Network overlay remains usable", "Live tiles are not required", "", f"HTTP P95: {q['p95_ms']:.1f} ms", f"Samples: {q['samples']}", "Target: <= 1,500 ms", "Production: not verified"])
    pdf.showPage()
    frame(3, "1:00 - Keep the negative result visible", "Older M0 fixture: scn_huh_exc_closed_am_peak. This is not the P3 shared-segment scenario.")
    image("02-simulation.png")
    old = evidence["scenarios"][0]
    notes(["Displayed from stored API data", "No injected replacement values", "No retuning for a better chart", "", f"Delay reduction: {old['delay_reduction_pct']}%", "Negative means guided is worse", "State the model boundary"])
    pdf.showPage()
    frame(4, "2:00 - Normal capacity: no benefit", "P3 shared directed segments / same frozen population, policy and seed")
    image("03-simulation.png")
    notes(["Baseline / guided", "Delay: 32,103.4 / 32,103.4", "Unit: person-minutes", "Served: 10,000 / 10,000", "Unmet: 0 / 0", "Delay reduction: 0%", "", "Three repeat runs match", "No benefit is a valid result"])
    pdf.showPage()
    frame(5, "3:00 - Stress capacity exposes the gap", "10% of simulated segment capacity - invented sensitivity, not observed spare capacity")
    image("04-simulation.png")
    notes(["Baseline / guided", "Delay: 125,121.6 / 123,138.1", "Unit: person-minutes", "Served: 9,690 / 9,801", "Unmet: 310 / 199", "Delay reduction: 1.6%", "Overloaded segments: 6 / 0", "", "Gap remains visible"])
    pdf.showPage()
    frame(6, "4:00 - State what the model cannot establish", "Fallback: local UI -> five-minute demo.webm in Edge/Chromium -> this PDF in a local reader")
    image("06-assumptions.png", width=560)
    notes(["No observed external passengers", "No wheelchair berth guarantee", "No train-by-train seat model", "No multi-window carryover", "Queue wait is an approximation", "", "Source: checked-in P3 results", "Environment: local isolated", "CI / production: separate records", "Final pitch deck: A + reviewer"], 626, 398)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42, 46, "Build base SHA: " + evidence["frontend_build"]["commit_sha"] + " (working changes recorded in package manifest)")
    pdf.showPage(); pdf.save()
    print(out.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
