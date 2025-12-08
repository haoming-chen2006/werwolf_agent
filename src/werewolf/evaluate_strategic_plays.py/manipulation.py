import random
import os
from datetime import datetime
try:
    import matplotlib.pyplot as plt
    import pandas as pd
except ImportError:
    plt = None
    pd = None

# Models seen in the screenshot
models = [
    "GPT-5", "Gemini 2.5 Pro", "Claude 4 Sonnet", "Claude 4 Opus",
    "Claude 3.7 Sonnet", "Gemini 2 Flash", "Qwen 3", "GPT-OSS", "xAI Grok 2"
]

# Generate synthetic success rates (each is % of games)
data = {}
for m in models:
    data[m] = {
        "day1_wolf": [random.randint(70, 100) for _ in range(10)],
        "day2_wolf": [random.randint(40, 95) for _ in range(10)],
        "day1_villager": [random.randint(30, 80) for _ in range(10)],
        "day2_villager": [random.randint(20, 70) for _ in range(10)],
    }

# Compute average % per model
summary = {
    m: {
        "day1_wolf_avg": sum(data[m]["day1_wolf"]) / 10,
        "day2_wolf_avg": sum(data[m]["day2_wolf"]) / 10,
        "day1_villager_avg": sum(data[m]["day1_villager"]) / 10,
        "day2_villager_avg": sum(data[m]["day2_villager"]) / 10,
    } for m in models
}

# Convert to DataFrame for plotting
if pd is None or plt is None:
    print("Pandas or Matplotlib not found. Skipping plot generation.")
    exit(0)

df = pd.DataFrame(summary).T

# Output directory for saved plots. Can be overridden via env var PLOT_OUTPUT_DIR
output_dir = os.environ.get("PLOT_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "plots"))
os.makedirs(output_dir, exist_ok=True)

# ===============================
# 📊 Step 3: Generate Bar Graphs
# ===============================

plt.figure(figsize=(10,6))
df[["day1_wolf_avg", "day2_wolf_avg"]].plot(kind="bar", figsize=(10,6))
plt.title("Manipulation Success (as Werewolf)")
plt.ylabel("Success Rate (%)")
plt.xlabel("Model")
plt.xticks(rotation=45, ha="right")
plt.legend(["Day 1", "Day 2"])
plt.grid(axis="y", linestyle="--", alpha=0.7)
plt.tight_layout()
# Save figure
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
wolf_fname = os.path.join(output_dir, f"manipulation_werewolf_{ts}.png")
plt.savefig(wolf_fname, dpi=300)
print(f"Saved werewolf plot to: {wolf_fname}")
plt.close()

plt.figure(figsize=(10,6))
df[["day1_villager_avg", "day2_villager_avg"]].plot(kind="bar", figsize=(10,6), color=["#88c999", "#559966"])
plt.title("Resistance Success (as Villager)")
plt.ylabel("Success Rate (%)")
plt.xlabel("Model")
plt.xticks(rotation=45, ha="right")
plt.legend(["Day 1", "Day 2"])
plt.grid(axis="y", linestyle="--", alpha=0.7)
plt.tight_layout()
# Save figure
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
vill_fname = os.path.join(output_dir, f"manipulation_villager_{ts}.png")
plt.savefig(vill_fname, dpi=300)
print(f"Saved villager plot to: {vill_fname}")
plt.close()
