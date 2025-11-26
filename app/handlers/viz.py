import matplotlib.pyplot as plt
import io
import base64
import pandas as pd

def make_plot_as_datauri(df: pd.DataFrame) -> str:
    """
    Simple helper: creates a PNG plot from the given dataframe and returns a base64 data URI.
    """
    fig, ax = plt.subplots()
    # pick first numeric column vs index or second numeric column
    numeric = df.select_dtypes(include=["number"])
    if numeric.shape[1] == 0:
        raise ValueError("No numeric columns to plot")
    if numeric.shape[1] == 1:
        numeric.plot(ax=ax)
    else:
        numeric.iloc[:, :2].plot(ax=ax)
    ax.set_title("Generated Chart")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    data = base64.b64encode(buf.read()).decode()
    return f"data:image/png;base64,{data}"
