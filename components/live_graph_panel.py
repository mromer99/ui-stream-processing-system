from dash import html, dcc, Input, Output, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import os
import plotly.express as px

# Build list of CSV files in results/
def list_result_csvs():
    files = []
    for fname in os.listdir("results"):
        if fname.lower().endswith(".csv"):
            files.append(fname)
    return sorted(files)

# Layout for the Live Graph panel
live_graph_panel = dbc.Card(
    dbc.CardBody(
        [
            html.H5("Live Graph", className="card-title"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("Select CSV"),
                                dcc.Dropdown(
                                    id="live-csv-dropdown",
                                    options=[{"label": f, "value": f} for f in list_result_csvs()],
                                    value=list_result_csvs()[0] if list_result_csvs() else None,
                                    clearable=False,
                                ),
                            ],
                            className="mb-3",
                        ),
                        width=9,
                    ),
                ]
            ),
            dcc.Graph(id="live-graph"),
            dcc.Interval(id="live-graph-interval", interval=5_000, n_intervals=0),
        ]
    ),
    style={"padding": "20px", "box-shadow": "0px 4px 8px rgba(0,0,0,0.1)"}
)

def register_live_graph_callbacks(app):
    @app.callback(
        Output("live-graph", "figure"),
        [Input("live-csv-dropdown", "value"),
         Input("live-graph-interval", "n_intervals")],
        prevent_initial_call=False
    )
    def update_live_graph(selected_csv, n):
        if not selected_csv:
            return {}
        path = os.path.join("results", selected_csv)
        try:
            df = pd.read_csv(path)
        except Exception:
            return {}
        # assume first two columns are X and Y
        x, y = df.columns[0], df.columns[1]
        fig = px.line(df, x=x, y=y, markers=True,
                      title=f"{y} over {x} — {selected_csv}")
        return fig
