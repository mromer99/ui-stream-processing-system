import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np

fig, ax = plt.subplots(1, 1, figsize=(16, 12))
ax.set_xlim(0, 16)
ax.set_ylim(0, 12)
ax.axis('off')

colors = {
    'main': '#FFE5B4',
    'component': '#B4E5FF',
    'utility': '#B4FFB4',
    'data': '#E5E5E5',
    'mqtt': '#FFB4D9',
    'config': '#FFB4E5'
}

def create_simple_box(ax, x, y, width, height, filename, file_type):
    box = FancyBboxPatch((x, y), width, height, 
                        boxstyle="round,pad=0.05", 
                        facecolor=colors[file_type], 
                        edgecolor='black', 
                        linewidth=1.5)
    ax.add_patch(box)
    
    display_name = filename.replace('.py', '').replace('_', '\n') if '.py' in filename else filename
    ax.text(x + width/2, y + height/2, display_name, 
           ha='center', va='center', fontsize=10, fontweight='bold')

def draw_simple_arrow(ax, from_pos, to_pos, color='blue', label=''):
    from_x, from_y = from_pos
    to_x, to_y = to_pos
    
    ax.annotate('', xy=(to_x, to_y), xytext=(from_x, from_y),
               arrowprops={'arrowstyle': '->', 'lw': 2, 'color': color, 'alpha': 0.7})
    
    if label:
        mid_x, mid_y = (from_x + to_x) / 2, (from_y + to_y) / 2
        ax.text(mid_x, mid_y, label, fontsize=8, ha='center', 
               bbox={'boxstyle': 'round,pad=0.3', 'facecolor': 'white', 'alpha': 0.8})

files = {
    'GUI Experiment\nTool': {'pos': (6, 7), 'size': (4, 1.5), 'type': 'main'},
    'NebulaStream UI\n(Query Editor)': {'pos': (1, 9), 'size': (3, 1.5), 'type': 'component'},
    'one_coordinator\nthree_workers.py': {'pos': (12, 9), 'size': (3, 1.5), 'type': 'component'},
    'dgen_read_bid.py\n(Data Generator)': {'pos': (1, 5.5), 'size': (3, 1.5), 'type': 'data'},
    'Sink.py\n(Latency Tracker)': {'pos': (12, 5.5), 'size': (3, 1.5), 'type': 'utility'},
    'MQTT Publish': {'pos': (2, 2.5), 'size': (3, 1.2), 'type': 'mqtt'},
    'MQTT Subscribe': {'pos': (11, 2.5), 'size': (3, 1.2), 'type': 'mqtt'},
    'MQTT Broker': {'pos': (6.5, 1), 'size': (3, 1), 'type': 'mqtt'},
}

file_positions = {}
for filename, props in files.items():
    x, y = props['pos']
    w, h = props['size']
    file_positions[filename] = (x + w/2, y + h/2)
    create_simple_box(ax, x, y, w, h, filename, props['type'])

relationships = [
    ('GUI Experiment\nTool', 'NebulaStream UI\n(Query Editor)', 'green', 'Query\nManagement'),
    ('GUI Experiment\nTool', 'one_coordinator\nthree_workers.py', 'blue', 'Start/Stop\nBenchmark'),
    ('GUI Experiment\nTool', 'dgen_read_bid.py\n(Data Generator)', 'purple', 'Control\nData Flow'),
    ('GUI Experiment\nTool', 'Sink.py\n(Latency Tracker)', 'orange', 'Collect\nMetrics'),
    ('dgen_read_bid.py\n(Data Generator)', 'MQTT Publish', 'red', 'Publish\nData'),
    ('MQTT Publish', 'MQTT Broker', 'red', ''),
    ('MQTT Broker', 'MQTT Subscribe', 'red', ''),
    ('MQTT Subscribe', 'one_coordinator\nthree_workers.py', 'red', 'Receive\nData'),
    ('Sink.py\n(Latency Tracker)', 'MQTT Subscribe', 'darkred', 'Subscribe to\nResults'),
]

for relationship in relationships:
    if len(relationship) == 4:
        from_file, to_file, color, label = relationship
    else:
        from_file, to_file, color = relationship
        label = ''
    
    if from_file in file_positions and to_file in file_positions:
        draw_simple_arrow(ax, file_positions[from_file], file_positions[to_file], color, label)

ax.text(8, 11.3, 'GUI Experiment Tool - System Architecture', 
       ha='center', va='center', fontsize=18, fontweight='bold')

legend_x, legend_y = 0.5, 0.3
legend_items = [
    ('Query Management', 'green'),
    ('Benchmark Control', 'blue'),
    ('Data Flow Control', 'purple'),
    ('Metrics Collection', 'orange'),
    ('MQTT Communication', 'red'),
]

ax.text(legend_x, legend_y + 0.4, 'Legend:', fontsize=10, fontweight='bold')
for i, (label_text, color) in enumerate(legend_items):
    y_offset = legend_y - i * 0.15
    ax.arrow(legend_x, y_offset, 0.3, 0, head_width=0.05, head_length=0.05, 
            fc=color, ec=color, alpha=0.7)
    ax.text(legend_x + 0.4, y_offset, label_text, fontsize=8, va='center')

ax.text(8, 0.1, 'System Communication: GUI Tool orchestrates components via MQTT pub/sub pattern', 
       ha='center', va='center', fontsize=11, style='italic')

plt.tight_layout()
plt.savefig('/home/omer/Desktop/Bachelorarbeit/Development/simple_file_relationship_diagram.png', 
           dpi=300, bbox_inches='tight', facecolor='white')
plt.show()

print("System Architecture Diagram saved as 'simple_file_relationship_diagram.png'")