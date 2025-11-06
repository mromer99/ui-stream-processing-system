# GUI Experiment Tool - Stream Processing System

A web-based GUI tool for benchmarking and monitoring stream processing systems. This tool provides real-time visualization of experiment results, network topology, and system performance metrics.

## Features

- **Experiment Configuration**: Configure and run benchmarks with customizable parameters
- **Live Results Monitoring**: Real-time latency tracking via MQTT
- **Container Stats**: Monitor CPU, memory, and network I/O of Docker containers/processes
- **Network Topology Visualization**: Interactive graph visualization of node relationships
- **Results Analysis**: Load and visualize CSV results with multiple plot styles

## Architecture

The system orchestrates five key components:
- **GUI Experiment Tool**: Central control interface
- **NebulaStream UI**: Query editor and management
- **Data Generator** (`dgen_read_bid.py`): Test data generation
- **Coordinator/Workers** (`one_coordinator_three_workers.py`): Stream processing
- **Latency Tracker** (`Sink.py`): Performance metrics collection

Communication between components uses MQTT publish/subscribe pattern for scalable, decoupled architecture.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/mromer99/ui-stream-processing-system.git
cd ui-stream-processing-system
```

2. Create and activate virtual environment:
```bash
python3 -m venv env
source env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python3 app.py
```

2. Open your browser and navigate to:
```
http://localhost:8050
```

3. Configure your experiment parameters:
   - Data Set
   - Query
   - Hardware Heterogeneity
   - Network Topology
   - Number of Nodes

4. Click "Start Experiment" to run the benchmark

## Project Structure

```
.
├── app.py                          # Main application entry point
├── components/
│   ├── experiment_panel.py         # Experiment configuration and control
│   ├── live_results_panel.py       # Live monitoring and container stats
│   ├── live_graph_panel.py         # Real-time graph visualization
│   └── results_panel.py            # Results analysis and plotting
├── assets/
│   └── cytoscape_mouse.js          # Interactive graph controls
├── runBenchmark.py                 # Benchmark execution script
├── simple_file_diagram.py          # System architecture diagram generator
├── requirements.txt                # Python dependencies
└── results/                        # Experiment results storage
```

## Configuration

MQTT Configuration (in `live_results_panel.py`):
- Broker: `172.19.0.1`
- Port: `1882`
- Topic: `q1-results`

## Requirements

- Python 3.x
- Dash and Dash Bootstrap Components
- Plotly
- Paho MQTT
- Pandas
- Matplotlib

See `requirements.txt` for complete list.

## System Diagram

Run the diagram generator to visualize the system architecture:
```bash
python3 simple_file_diagram.py
```

## License

This project was developed as part of a Bachelor's thesis (Bachelorarbeit).

## Author

mromer99
