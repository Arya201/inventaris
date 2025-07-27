from flask import Flask, render_template, jsonify, request
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import warnings
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import sklearn.metrics as metrics
from flask_cors import CORS  # <── Tambahkan import CORS

warnings.filterwarnings('ignore')

app = Flask(__name__)
# <── Izinkan CORS
CORS(app, resources={
     r"/api/*": {"origins": ["http://localhost", "http://127.0.0.1"]}})

# ======================
# Konfigurasi Database
# ======================
host = 'localhost'
user = 'root'
password = ''
database = 'inventaris'

engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}/{database}')
query = 'SELECT * FROM gudang where keterangan="terjual"'

# ======================
# Helper Functions
# ======================


def prepare_series(period: str = 'M') -> pd.Series:
    """Ambil data, filter, resample, interpolasi."""
    df_ori = pd.read_sql(query, engine, parse_dates=['tanggal'])
    df_ori['tanggal'] = pd.to_datetime(df_ori['tanggal'].dt.date)

    # Group by date and sum the values to handle duplicates
    df_grouped = df_ori.groupby('tanggal')['barang_keluar'].sum().reset_index()
    df_grouped.set_index('tanggal', inplace=True)
    series = df_grouped['barang_keluar'].copy()

    # Get min/max from the index (not column)
    awal = series.index.min()
    akhir = series.index.max()
    series = series[awal:akhir]

    series_resampled = series.resample(period).sum()
    series_resampled.interpolate(inplace=True)
    return series_resampled


def arima_predict(series: pd.Series, period: str = 'M', future_steps: int = 12, order: tuple = (1, 2, 2)):
    split_point = int(len(series) * 0.7)
    train, test = series.iloc[:split_point], series.iloc[split_point:]

    model = ARIMA(train, order=order)
    model_fit = model.fit()

    pred_test = model_fit.predict(start=test.index[0], end=test.index[-1])

    last_date = series.index[-1]
    if period == 'M':
        future_dates = pd.date_range(
            start=last_date + pd.offsets.MonthBegin(), periods=future_steps, freq='M')
    elif period == 'W':
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(weeks=1), periods=future_steps, freq='W')
    else:
        raise ValueError('Unsupported period')

    pred_future = model_fit.predict(
        start=future_dates[0], end=future_dates[-1])
    pred_all = pd.concat([pred_test, pred_future])

    mape = metrics.mean_absolute_percentage_error(test, pred_test) * 100
    rmse = np.sqrt(np.mean((test.values - pred_test.values) ** 2))

    return pred_all, round(mape, 2), round(rmse, 2)


def series_to_json(series: pd.Series, fmt: str):
    return [{"tanggal": idx.strftime(fmt), "value": val} for idx, val in series.items()]

# ======================
# Routes
# ======================


@app.route('/')
def index():
    return render_template('dashboard.html')

# Bulanan


@app.route('/api/data')
def api_data_monthly():
    series = prepare_series('M')
    return jsonify(series_to_json(series, '%Y-%m'))


@app.route('/api/predict', methods=['POST'])
def api_predict_monthly():
    series = prepare_series('M')
    pred_all, mape, rmse = arima_predict(series, 'M', 12)
    return jsonify({
        'prediksi': series_to_json(pred_all, '%Y-%m'),
        'metrics': {'MAPE': mape, 'RMSE': rmse}
    })

# Mingguan


@app.route('/api/data-weekly')
def api_data_weekly():
    series = prepare_series('W')
    return jsonify(series_to_json(series, '%Y-%m-%d'))


@app.route('/api/predict-weekly', methods=['POST'])
def api_predict_weekly():
    series = prepare_series('W')
    pred_all, mape, rmse = arima_predict(series, 'W', 12)
    return jsonify({
        'prediksi': series_to_json(pred_all, '%Y-%m-%d'),
        'metrics': {'MAPE': mape, 'RMSE': rmse}
    })

# ======================
# Main
# ======================


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
