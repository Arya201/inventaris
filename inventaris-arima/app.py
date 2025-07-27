from flask import Flask, request, jsonify, send_file, make_response
import pandas as pd
from sqlalchemy import create_engine, text
from flask_cors import CORS
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from fpdf import FPDF
import datetime
# Konfigurasi Flask dan CORS
app = Flask(__name__)
CORS(app, resources={
    r"/laporan": {
        "origins": ["http://localhost", "http://127.0.0.1"],
        "methods": ["GET", "POST"],  # Tambahkan GET
        "allow_headers": ["Content-Type"]
    },
    r"/*": {
        "origins": "*",
        "supports_credentials": True
    }
})


# Konfigurasi koneksi database MySQL
host = 'localhost'
user = 'root'
password = ''
database = 'inventaris'

engine = create_engine(
    f'mysql+pymysql://{user}:{password}@{host}/{database}', echo=True
)

# ===============================
# Barang: GET dan POST dalam 1 route
# ===============================


@app.route('/barang', methods=['GET', 'POST'])
def handle_barang():
    if request.method == 'GET':
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT * FROM master_barang")).fetchall()
            data = [dict(row._mapping) for row in result]
        return jsonify(data)

    elif request.method == 'POST':
        try:
            data = request.get_json()
            nama = data.get("nama")
            satuan = data.get("satuan")
            harga = data.get("harga")
            qty = data.get("qty")

            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO master_barang (nama_barang, satuan, harga_barang, qty)
                    VALUES (:nama, :satuan, :harga, :qty)
                """), {
                    'nama': nama,
                    'satuan': satuan,
                    'harga': harga,
                    'qty': qty
                })
            return jsonify({"message": "Barang berhasil ditambahkan"}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# ===============================
# Update Barang
# ===============================


@app.route('/barang/<int:id>', methods=['PUT'])
def update_barang(id):
    try:
        data = request.get_json()
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE master_barang
                SET nama_barang=:nama, satuan=:satuan, harga_barang=:harga
                WHERE id_barang=:id
            """), {
                'nama': data['nama'],
                'satuan': data['satuan'],
                'harga': data['harga'],
                'id': id
            })
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===============================
# Hapus Barang
# ===============================


@app.route('/barang/<int:id>', methods=['DELETE'])
def hapus_barang(id):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM master_barang WHERE id_barang=:id"), {"id": id})
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===============================
# Transaksi: GET
# ===============================


@app.route('/transaksi', methods=['GET'])
def ambil_transaksi():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT g.*, m.nama_barang 
                FROM gudang g 
                JOIN master_barang m ON g.id_barang = m.id_barang
                ORDER BY g.tanggal DESC
            """)).fetchall()
        return jsonify([dict(row._mapping) for row in result])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===============================
# Transaksi: POST
# ===============================


@app.route('/transaksi', methods=['POST'])
def proses_transaksi():
    try:
        data = request.get_json()
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO gudang (tanggal, id_barang, barang_masuk, barang_keluar, keterangan)
                VALUES (:tanggal, :id_barang, :barang_masuk, :barang_keluar, :keterangan)
            """), data)
            conn.execute(text("""
                UPDATE master_barang
                SET qty = qty + :barang_masuk - :barang_keluar
                WHERE id_barang = :id_barang
            """), data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===============================
# Transaksi Tambahan: hanya jika dibutuhkan
# ===============================


@app.route('/transaksi-data', methods=['GET'])
def api_transaksi_data():
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT g.*, m.nama_barang FROM gudang g
                JOIN master_barang m ON m.id_barang = g.id_barang
                ORDER BY g.tanggal DESC
            """)).mappings().all()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/laporan', methods=['GET', 'POST'])
def generate_laporan_pdf():
    try:
        if request.method == 'POST':
            data = request.get_json()
        else:
            # Ambil parameter dari URL untuk preview
            data = {
                'tanggal_awal': request.args.get('tanggal_awal'),
                'tanggal_akhir': request.args.get('tanggal_akhir'),
                'report_type': request.args.get('report_type', 'all')
            }

        tanggal_awal = data.get('tanggal_awal')
        tanggal_akhir = data.get('tanggal_akhir')
        report_type = data.get('report_type', 'all')

        if not tanggal_awal or not tanggal_akhir:
            return jsonify({"error": "Tanggal awal dan akhir wajib diisi"}), 400

        # Query tetap sama
        query = """
            SELECT g.tanggal, m.nama_barang, g.barang_masuk, g.barang_keluar, g.keterangan
            FROM gudang g
            JOIN master_barang m ON g.id_barang = m.id_barang
            WHERE g.tanggal BETWEEN :start AND :end
        """
        if report_type == 'in':
            query += " AND g.barang_masuk > 0"
        elif report_type == 'out':
            query += " AND g.barang_keluar > 0"
        query += " ORDER BY g.tanggal ASC"

        with engine.begin() as conn:
            result = conn.execute(
                text(query), {'start': tanggal_awal, 'end': tanggal_akhir}).fetchall()
            data_rows = [dict(row._mapping) for row in result]

        # Generate PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Laporan Transaksi Barang", ln=True, align="C")
        pdf.set_font("Arial", '', 10)
        pdf.cell(
            0, 10, f"Tanggal: {tanggal_awal} s/d {tanggal_akhir}", ln=True)

        # Header
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(30, 8, "Tanggal", 1, 0, 'C', 1)
        pdf.cell(50, 8, "Barang", 1, 0, 'C', 1)
        pdf.cell(25, 8, "Masuk", 1, 0, 'C', 1)
        pdf.cell(25, 8, "Keluar", 1, 0, 'C', 1)
        pdf.cell(50, 8, "Keterangan", 1, 1, 'C', 1)

        pdf.set_font("Arial", '', 9)
        for row in data_rows:
            pdf.cell(30, 8, str(row['tanggal']), 1)
            pdf.cell(50, 8, str(row['nama_barang']), 1)
            pdf.cell(25, 8, str(row['barang_masuk']), 1, 0, 'C')
            pdf.cell(25, 8, str(row['barang_keluar']), 1, 0, 'C')
            pdf.cell(50, 8, str(row['keterangan']), 1, 1)

        # Simpan PDF ke BytesIO (dengan cara FPDF yang benar)
        pdf_output = pdf.output(dest='S').encode(
            'latin1')  # Wajib encode latin1
        output = BytesIO(pdf_output)

        filename = f"Laporan_{tanggal_awal}_to_{tanggal_akhir}.pdf"
        return send_file(output, download_name=filename, as_attachment=False)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===============================
# Jalankan server Flask
# ===============================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
