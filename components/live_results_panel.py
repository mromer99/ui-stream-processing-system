import threading
import json
import time
from datetime import datetime
from collections import deque
import subprocess

import paho.mqtt.client as mqtt
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

class MQTTConfig:
    BROKER = "172.19.0.1"
    PORT = 1882
    TOPIC = "q1-results"

class MonitoringConfig:
    MAX_LATENCY_POINTS = 500
    MAX_STATS_POINTS = 50
    UPDATE_INTERVAL_MS = 2000
    STATS_INTERVAL_MS = 3000

class DataStorage:
    def __init__(self):
        self.timestamps = deque(maxlen=MonitoringConfig.MAX_LATENCY_POINTS)
        self.latencies = deque(maxlen=MonitoringConfig.MAX_LATENCY_POINTS)
        self.connection_status = {"connected": False, "last_error": "Not connected yet"}
        self.container_stats = {}

    def add_latency_data(self, timestamp, latency):
        self.timestamps.append(timestamp)
        self.latencies.append(latency)

    def update_connection_status(self, connected, error=None):
        self.connection_status["connected"] = connected
        self.connection_status["last_error"] = error

    def get_container_stats(self, container_name):
        if container_name not in self.container_stats:
            self.container_stats[container_name] = {
                'cpu': deque(maxlen=MonitoringConfig.MAX_STATS_POINTS),
                'memory': deque(maxlen=MonitoringConfig.MAX_STATS_POINTS),
                'net_rx': deque(maxlen=MonitoringConfig.MAX_STATS_POINTS),
                'net_tx': deque(maxlen=MonitoringConfig.MAX_STATS_POINTS),
                'timestamps': deque(maxlen=MonitoringConfig.MAX_STATS_POINTS)
            }
        return self.container_stats[container_name]

    def add_container_stats(self, container_name, cpu, memory, net_rx, net_tx, timestamp):
        stats = self.get_container_stats(container_name)
        stats['cpu'].append(cpu)
        stats['memory'].append(memory)
        stats['net_rx'].append(net_rx)
        stats['net_tx'].append(net_tx)
        stats['timestamps'].append(timestamp)
        

data_storage = DataStorage()

class DockerManager:
    @staticmethod
    def check_permission():
        try:
            result = subprocess.run(["docker", "version"], capture_output=True, text=True)
            if result.returncode == 0:
                return True, None
            else:
                return False, f"Docker daemon not accessible: {result.stderr.strip()}"
        except FileNotFoundError:
            return False, "Docker not installed"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_container_names():
        has_permission, error = DockerManager.check_permission()
        if not has_permission:
            print(f"Docker permission error: {error}")
            return ProcessManager.get_process_names()
        
        try:
            names = subprocess.check_output(
                ["docker", "ps", "--format", "{{.Names}}"],
                stderr=subprocess.STDOUT
            ).decode().splitlines()
            return names
        except Exception as e:
            print(f"Error getting container names: {e}")
            return ProcessManager.get_process_names()

    @staticmethod
    def get_container_stats(container_name):
        has_permission, _ = DockerManager.check_permission()
        if has_permission:
            try:
                result = subprocess.run([
                    "docker", "stats", "--no-stream", "--format", 
                    "{{.CPUPerc}}|{{.MemPerc}}|{{.NetIO}}", container_name
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output and '|' in output:
                        parts = output.split("|")
                        if len(parts) == 3:
                            cpu_str, mem_str, net_str = parts
                            cpu_val = float(cpu_str.replace('%', ''))
                            mem_val = float(mem_str.replace('%', ''))
                            
                            # Parse network I/O (format: "1.2kB / 3.4MB")
                            net_rx, net_tx = DockerManager._parse_network_io(net_str)
                            
                            return cpu_val, mem_val, net_rx, net_tx, None
            except Exception:
                pass
        
        # Fallback to process stats (no network I/O for processes)
        cpu, memory, net_rx, net_tx, error = ProcessManager.get_process_stats(container_name)
        return cpu, memory, net_rx, net_tx, error
    
    @staticmethod
    def _parse_network_io(net_str):
        """Parse network I/O string like '1.2kB / 3.4MB' and return values in bytes"""
        try:
            parts = net_str.split(' / ')
            if len(parts) == 2:
                rx_str, tx_str = parts[0].strip(), parts[1].strip()
                rx_bytes = DockerManager._convert_to_bytes(rx_str)
                tx_bytes = DockerManager._convert_to_bytes(tx_str)
                return rx_bytes, tx_bytes
        except Exception:
            pass
        return 0.0, 0.0
    
    @staticmethod
    def _convert_to_bytes(size_str):
        """Convert size string like '1.2kB' to bytes"""
        try:
            size_str = size_str.replace('B', '')
            multiplier = 1
            
            if size_str.endswith('k'):
                multiplier = 1024
                size_str = size_str[:-1]
            elif size_str.endswith('M'):
                multiplier = 1024 * 1024
                size_str = size_str[:-1]
            elif size_str.endswith('G'):
                multiplier = 1024 * 1024 * 1024
                size_str = size_str[:-1]
            elif size_str.endswith('T'):
                multiplier = 1024 * 1024 * 1024 * 1024
                size_str = size_str[:-1]
            
            return float(size_str) * multiplier
        except Exception:
            return 0.0

class ProcessManager:
    @staticmethod
    def get_process_names():
        try:
            result = subprocess.run(["ps", "aux", "--no-headers"], capture_output=True, text=True)
            if result.returncode != 0:
                return []
            
            processes = []
            process_info = {}
            
            for line in result.stdout.splitlines():
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    user, pid, cpu, mem, cmd = parts[0], parts[1], parts[2], parts[3], parts[10]
                    
                    if ProcessManager._is_monitorable_process(cmd):
                        process_name = ProcessManager._extract_process_name(cmd, pid)
                        processes.append(process_name)
                        process_info[process_name] = {'pid': pid, 'user': user, 'cmd': cmd}
            
            ProcessManager._log_found_processes(processes, process_info)
            return processes[:15]
            
        except Exception as e:
            print(f"Error getting process names: {e}")
            return []

    @staticmethod
    def _is_monitorable_process(cmd):
        keywords = ['java', 'python', 'node', 'nginx', 'kafka', 'flink', 'docker', 'container']
        return any(keyword in cmd.lower() for keyword in keywords)

    @staticmethod
    def _extract_process_name(cmd, pid):
        cmd_lower = cmd.lower()
        
        if 'java' in cmd_lower:
            return ProcessManager._extract_java_name(cmd, pid)
        elif 'python' in cmd_lower:
            return ProcessManager._extract_python_name(cmd, pid)
        else:
            cmd_first = cmd.split()[0].split('/')[-1]
            return f"{cmd_first}-{pid}"

    @staticmethod
    def _extract_java_name(cmd, pid):
        if '.jar' in cmd:
            jar_parts = [p for p in cmd.split() if '.jar' in p]
            if jar_parts:
                jar_name = jar_parts[0].split('/')[-1].replace('.jar', '')
                return f"java-{jar_name}"
        else:
            for part in cmd.split():
                if part.startswith('org.') or part.startswith('com.'):
                    main_class = part.split('.')[-1]
                    return f"java-{main_class}"
        return f"java-{pid}"

    @staticmethod
    def _extract_python_name(cmd, pid):
        if '.py' in cmd:
            py_parts = [p for p in cmd.split() if '.py' in p]
            if py_parts:
                py_name = py_parts[0].split('/')[-1].replace('.py', '')
                return f"python-{py_name}"
        return f"python-{pid}"

    @staticmethod
    def _log_found_processes(processes, process_info):
        print(f"Found {len(processes)} processes for monitoring:")
        for proc in processes[:5]:
            cmd = process_info.get(proc, {}).get('cmd', '')
            print(f"  - {proc}: {cmd[:80]}...")

    @staticmethod
    def get_process_stats(process_pattern):
        pid = ProcessManager._extract_pid_from_pattern(process_pattern)
        
        if pid:
            return ProcessManager._get_stats_by_pid(pid)
        else:
            return ProcessManager._get_stats_by_pattern(process_pattern)

    @staticmethod
    def _extract_pid_from_pattern(process_pattern):
        if '-' in process_pattern:
            parts = process_pattern.split('-')
            try:
                return int(parts[-1])
            except ValueError:
                pass
        return None

    @staticmethod
    def _get_stats_by_pid(pid):
        try:
            result = subprocess.run([
                "ps", "-p", str(pid), "-o", "pid,pcpu,pmem,comm", "--no-headers"
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split()
                if len(parts) >= 3:
                    cpu = float(parts[1])
                    mem = float(parts[2])
                    return cpu, mem, 0.0, 0.0, None
            else:
                return None, None, 0.0, 0.0, f"Process with PID {pid} not found"
                
        except ValueError as e:
            return None, None, 0.0, 0.0, f"Parse error for PID {pid}: {e}"
        except Exception as e:
            return None, None, 0.0, 0.0, f"Error getting process stats: {str(e)}"

    @staticmethod
    def _get_stats_by_pattern(process_pattern):
        try:
            result = subprocess.run(["ps", "aux", "--no-headers"], capture_output=True, text=True)
            if result.returncode != 0:
                return None, None, 0.0, 0.0, "ps command failed"
            
            total_cpu = 0.0
            total_mem = 0.0
            process_count = 0
            search_terms = process_pattern.lower().split('-')
            
            for line in result.stdout.splitlines():
                if any(term in line.lower() for term in search_terms if term):
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            total_cpu += float(parts[2])
                            total_mem += float(parts[3])
                            process_count += 1
                        except ValueError:
                            continue
            
            if process_count == 0:
                return None, None, 0.0, 0.0, f"No processes found matching '{process_pattern}'"
            
            return total_cpu, total_mem, 0.0, 0.0, None
            
        except Exception as e:
            return None, None, 0.0, 0.0, f"Error getting process stats: {str(e)}"

class MQTTClient:
    def __init__(self, data_storage):
        self.data_storage = data_storage
        self.client = None
        self.retry_interval = 5
        self.max_retry_interval = 60

    def start(self):
        threading.Thread(target=self._run_mqtt_loop, daemon=True).start()

    def _run_mqtt_loop(self):
        self.client = mqtt.Client()
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        while True:
            try:
                self.client.connect(MQTTConfig.BROKER, MQTTConfig.PORT, 60)
                self.retry_interval = 5
                self.client.loop_forever()
            except Exception as e:
                self.data_storage.update_connection_status(False, f"MQTT error: {e}")
                time.sleep(self.retry_interval)
                self.retry_interval = min(self.retry_interval * 2, self.max_retry_interval)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
            pub_ts = datetime.fromtimestamp(float(data["bid$timestamp"]) / 1000.0)
            now = datetime.now()
            latency_ms = (now - pub_ts).total_seconds() * 1000
            self.data_storage.add_latency_data(now, latency_ms)
        except Exception as e:
            print("MQTT message processing error:", e)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.data_storage.update_connection_status(True)
            client.subscribe(MQTTConfig.TOPIC)
        else:
            self.data_storage.update_connection_status(False, f"Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        error_msg = f"Disconnected with error code {rc}" if rc != 0 else "Disconnected"
        self.data_storage.update_connection_status(False, error_msg)

class UIComponents:
    @staticmethod
    def create_docker_status_alert():
        docker_available, docker_error = DockerManager.check_permission()
        
        if docker_available:
            return html.Div()
        
        return dbc.Alert([
            html.H6("Docker Status:", className="alert-heading"),
            html.P(f"Not Available - {docker_error}"),
            html.Hr(),
            html.Div([
                html.P("To enable full Docker monitoring:"),
                html.Ul([
                    html.Li("1. sudo usermod -aG docker $USER"),
                    html.Li("2. Log out and log back in (or restart)"),
                    html.Li("3. Verify with: docker ps")
                ])
            ]),
            html.P("Using alternative process monitoring for now.")
        ], color="warning", className="mb-3")

    @staticmethod
    def create_process_dropdown():
        names = DockerManager.get_container_names()
        
        return dbc.Row(
            dbc.Col(
                dbc.InputGroup([
                    dbc.InputGroupText("Select Process/Container"),
                    dcc.Dropdown(
                        id="container-dropdown",
                        options=[{"label": n, "value": n} for n in names],
                        value=names[0] if names else None,
                        clearable=False,
                        placeholder="No processes found" if not names else "Select a process...",
                        style={"minWidth": "300px"}
                    ),
                ], className="mb-3"),
                width=10,
            )
        )

    @staticmethod
    def create_monitoring_graphs():
        return dbc.Row([
            dbc.Col([
                html.H6("CPU Usage"),
                html.Div(id="cpu-live-value", className="h4 text-primary"),
                dcc.Graph(id="cpu-live-graph", style={"height": "200px"})
            ], width=6),
            dbc.Col([
                html.H6("Memory Usage"),
                html.Div(id="mem-live-value", className="h4 text-success"),
                dcc.Graph(id="mem-live-graph", style={"height": "200px"})
            ], width=6),
        ])

    @staticmethod
    def create_network_monitoring_graphs():
        return dbc.Row([
            dbc.Col([
                html.H6("Network RX (Received)"),
                html.Div(id="net-rx-live-value", className="h4 text-info"),
                dcc.Graph(id="net-rx-live-graph", style={"height": "200px"})
            ], width=6),
            dbc.Col([
                html.H6("Network TX (Transmitted)"),
                html.Div(id="net-tx-live-value", className="h4 text-warning"),
                dcc.Graph(id="net-tx-live-graph", style={"height": "200px"})
            ], width=6),
        ])

class GraphCreator:
    @staticmethod
    def create_latency_graph(timestamps, latencies):
        if not timestamps:
            fig = px.line(title="End-to-End Event Latency")
            fig.update_layout(annotations=[{
                "text": "Waiting for data...",
                "xref": "paper", "yref": "paper",
                "showarrow": False, "font": {"size": 20}
            }])
            return fig
        
        fig = px.line(
            x=list(timestamps), 
            y=list(latencies), 
            labels={"x": "Time", "y": "Latency (ms)"}, 
            title="End-to-End Event Latency"
        )
        fig.update_traces(mode="markers+lines")
        return fig

    @staticmethod
    def create_stats_graph(timestamps, values, title, color, y_title):
        if len(timestamps) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(timestamps),
                y=list(values),
                mode='lines+markers',
                line=dict(color=color),
                marker=dict(size=4)
            ))
            fig.update_layout(
                title=title,
                yaxis_title=y_title,
                showlegend=False,
                margin=dict(l=40, r=20, t=40, b=30),
                yaxis=dict(range=[0, max(100, max(values) * 1.1) if values else 100])
            )
            return fig
        else:
            fig = go.Figure()
            fig.update_layout(
                title=title,
                showlegend=False,
                margin=dict(l=40, r=20, t=40, b=30),
                annotations=[{
                    "text": "Collecting data...",
                    "xref": "paper", "yref": "paper",
                    "showarrow": False, "font": {"size": 12}
                }]
            )
            return fig

    @staticmethod
    def create_empty_graph(title, message="Select a process to monitor"):
        fig = go.Figure()
        fig.update_layout(
            title=title,
            showlegend=False,
            xaxis={'visible': False},
            yaxis={'visible': False},
            annotations=[{
                "text": message,
                "xref": "paper", "yref": "paper",
                "showarrow": False, "font": {"size": 14}
            }]
        )
        return fig

class NetworkUtils:
    @staticmethod
    def format_bytes(bytes_value):
        """Format bytes to human readable format"""
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        value = float(bytes_value)
        
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(value)} {units[unit_index]}"
        else:
            return f"{value:.1f} {units[unit_index]}"

mqtt_client = MQTTClient(data_storage)
mqtt_client.start()

live_results_panel = dbc.Card(
    dbc.CardBody([
        html.Div([
            html.H5("Live Sink Latency", className="card-title d-inline"),
            html.Div(id="mqtt-connection-status", className="float-right")
        ], className="d-flex justify-content-between align-items-center"),
        dcc.Graph(id="live-results-graph"),
        dcc.Interval(id="live-results-interval", interval=MonitoringConfig.UPDATE_INTERVAL_MS, n_intervals=0),
        html.Hr(),
        html.H5("Container Stats", className="card-title"),
        UIComponents.create_docker_status_alert(),
        UIComponents.create_process_dropdown(),
        UIComponents.create_monitoring_graphs(),
        html.Hr(),
        html.H5("Network I/O", className="card-title"),
        UIComponents.create_network_monitoring_graphs(),
        dcc.Interval(id="container-stats-interval", interval=MonitoringConfig.STATS_INTERVAL_MS, n_intervals=0),
    ]),
    style={"padding": "20px", "box-shadow": "0px 4px 8px rgba(0,0,0,0.1)"}
)

def register_live_results_callbacks(app):
    @app.callback(
        [Output("live-results-graph", "figure"), Output("mqtt-connection-status", "children")],
        Input("live-results-interval", "n_intervals"),
    )
    def update_live_results(n):
        status = data_storage.connection_status
        if status["connected"]:
            status_badge = dbc.Badge("Connected", color="success", className="ml-2")
        else:
            err = status["last_error"] or "Connection error"
            status_badge = dbc.Badge(f"Disconnected: {err}", color="danger", className="ml-2")
        
        fig = GraphCreator.create_latency_graph(data_storage.timestamps, data_storage.latencies)
        return fig, status_badge

    @app.callback(
        [Output("cpu-live-value", "children"), 
         Output("mem-live-value", "children"),
         Output("cpu-live-graph", "figure"),
         Output("mem-live-graph", "figure")],
        [Input("container-dropdown", "value"), Input("container-stats-interval", "n_intervals")],
    )
    def update_container_stats(selected, n):
        if not selected:
            empty_fig = GraphCreator.create_empty_graph("No Process Selected")
            return "N/A", "N/A", empty_fig, empty_fig
        
        cpu, memory, net_rx, net_tx, error = DockerManager.get_container_stats(selected)
        
        if n % 5 == 0:
            print(f"Monitoring {selected}: CPU={cpu}, Memory={memory}, NetRX={net_rx}, NetTX={net_tx}, Error={error}")
        
        if error is None and cpu is not None and memory is not None:
            data_storage.add_container_stats(selected, cpu, memory, net_rx, net_tx, datetime.now())
            cpu_display = f"{cpu:.1f}%"
            mem_display = f"{memory:.1f}%"
        else:
            cpu_display = "Error"
            mem_display = "Error"
        
        stats = data_storage.get_container_stats(selected)
        cpu_fig = GraphCreator.create_stats_graph(
            stats['timestamps'], stats['cpu'], f"CPU Usage: {selected}", '#1f77b4', "CPU %"
        )
        mem_fig = GraphCreator.create_stats_graph(
            stats['timestamps'], stats['memory'], f"Memory Usage: {selected}", '#2ca02c', "Memory %"
        )
        
        return cpu_display, mem_display, cpu_fig, mem_fig

    @app.callback(
        [Output("net-rx-live-value", "children"), 
         Output("net-tx-live-value", "children"),
         Output("net-rx-live-graph", "figure"),
         Output("net-tx-live-graph", "figure")],
        [Input("container-dropdown", "value"), Input("container-stats-interval", "n_intervals")],
    )
    def update_network_stats(selected, n):
        if not selected:
            empty_fig = GraphCreator.create_empty_graph("No Process Selected")
            return "N/A", "N/A", empty_fig, empty_fig
        
        _, _, net_rx, net_tx, error = DockerManager.get_container_stats(selected)
        
        if error is None and net_rx is not None and net_tx is not None:
            net_rx_display = NetworkUtils.format_bytes(net_rx)
            net_tx_display = NetworkUtils.format_bytes(net_tx)
        else:
            net_rx_display = "Error" if selected.startswith('java-') or selected.startswith('python-') else "N/A"
            net_tx_display = "Error" if selected.startswith('java-') or selected.startswith('python-') else "N/A"
        
        stats = data_storage.get_container_stats(selected)
        
        # Convert bytes to KB for better visualization
        net_rx_kb = [bytes_val / 1024 for bytes_val in stats['net_rx']]
        net_tx_kb = [bytes_val / 1024 for bytes_val in stats['net_tx']]
        
        net_rx_fig = GraphCreator.create_stats_graph(
            stats['timestamps'], net_rx_kb, f"Network RX: {selected}", '#17a2b8', "KB"
        )
        net_tx_fig = GraphCreator.create_stats_graph(
            stats['timestamps'], net_tx_kb, f"Network TX: {selected}", '#ffc107', "KB"
        )
        
        return net_rx_display, net_tx_display, net_rx_fig, net_tx_fig

