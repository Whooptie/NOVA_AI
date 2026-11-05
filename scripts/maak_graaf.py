import json
from modules.knowledge import graph_render_3d

with open("data/concepts.json", encoding="utf-8") as f:
    concepten = json.load(f)

print(graph_render_3d.schrijf_html_3d(concepten, "fiets"))