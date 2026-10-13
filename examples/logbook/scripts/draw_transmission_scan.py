"""The example entry's figure. Run from the lab-templates root:
    uv run --with matplotlib python examples/logbook/scripts/draw_transmission_scan.py
labfig never overwrites a version: delete the -v1 files first to redraw it."""
import sys
sys.path.insert(0, "matplotlib")  # run from the lab-templates root
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import labfig
labfig.style()
rows = list(csv.DictReader(open("examples/logbook/entries/2026/data/transmission-scan-r017.csv")))
x = [float(r["extract_V"]) for r in rows]; y = [float(r["transmission_percent"]) for r in rows]
fig, ax = plt.subplots()
ax.plot(x, y, "o-", color="#00A2FF")
ax.set_xlabel("Extraction voltage (V)", fontweight="bold")
ax.set_ylabel("Transmission (%)", fontweight="bold")
ax.annotate("maximum 38 % at −120 V", xy=(-120, 38.1), xytext=(-138, 37), arrowprops=dict(arrowstyle="->"))
labfig.save(fig, "examples/logbook/entries/2026/figures/plot-example-transmission-scan", version=1,
            author="A. Author", created="2026-10-01", data=["examples/logbook/entries/2026/data/transmission-scan-r017.csv"],
            code=None)  # the script is in git: no copy
