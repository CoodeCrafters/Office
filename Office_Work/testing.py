from flask import Flask, request, jsonify
import pandas as pd
from io import BytesIO, StringIO
import re
import time
import os
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)

ALLOWED_ORIGIN = "https://coodecrafters.github.io"

# Enable CORS using Flask-CORS (optional fallback)
CORS(app, resources={r"/*": {"origins": [ALLOWED_ORIGIN]}})
# Keepalive endpoint
@app.route('/keepalive', methods=['GET'])
def keepalive():
    return jsonify({
        "status": "active",
        "message": "Welcome to Incredible platform",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    

# Brand mapping
BRAND_MAPPING = {
    "SFERA": "1000020410",
    "WOMEN SECRET": "1000027886",
    "STRADIVARIUS AL MARYAH": "1000058592",
    "SPRINGFIELD": "1000239457",
    "ZARA HOME": "1000175313",
    "LEFTIES": "1000175297"
}

def extract_date_from_filename(filename):
    match = re.search(r'(\d{2}\.\d{2}\.\d{2})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%d.%m.%y').strftime('%d-%m-%Y')
        except:
            return None
    return None

@app.route('/retrieve', methods=['POST', 'OPTIONS'])
def retrieve_data():
    try:
        if request.method == 'OPTIONS':
            return '', 204
            
        if 'excelFile' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['excelFile']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        file_date = extract_date_from_filename(file.filename)

        filename = file.filename.lower()
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(StringIO(file.read().decode('utf-8')), header=None)
                sheets = {'csv_data': df}
            else:
                excel_data = pd.ExcelFile(BytesIO(file.read()))
                sheets = {sheet_name: pd.read_excel(excel_data, sheet_name=sheet_name, header=None)
                          for sheet_name in excel_data.sheet_names}
        except Exception as e:
            return jsonify({"error": f"Error reading file: {str(e)}"}), 400

        results = {}

        for sheet_name, df in sheets.items():
            header_rows = df[df[0] == "HD"].index

            for header_row in header_rows:
                brand_name = str(df.iloc[header_row, 13]).strip().upper()

                if brand_name in BRAND_MAPPING:
                    merchant_id = BRAND_MAPPING[brand_name]
                    outlet_name = str(df.iloc[header_row, 14]).strip()

                    dt_rows = df[
                        (df[0] == "DT") &
                        (df[1].astype(str) == merchant_id) &
                        (df.index > header_row)
                    ]

                    if not dt_rows.empty:
                        extracted_data = dt_rows[[19, 21, 35]].copy()
                        extracted_data.columns = ['COMM_AMOUNT', 'VAT_AMOUNT', 'SETT_AMOUNT']
                        extracted_data = extracted_data.apply(pd.to_numeric, errors='coerce').fillna(0)

                        totals = extracted_data.sum()

                        results[merchant_id] = {
                            "brand_name": brand_name,
                            "company_outlet_name": outlet_name,
                            "merchant_id": merchant_id,
                            "COMM_AMOUNT": round(float(totals['COMM_AMOUNT']), 2),
                            "VAT_AMOUNT": round(float(totals['VAT_AMOUNT']), 2),
                            "SETT_AMOUNT": round(float(totals['SETT_AMOUNT']), 2),
                            "transaction_details": extracted_data.to_dict('records'),
                            "date": file_date
                        }

        if not results:
            return jsonify({"error": "No matching data found in the file"}), 404

        response = jsonify({
            "status": "success",
            "date": file_date,
            "data": list(results.values())
        })
        return response
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Ensure all responses carry CORS headers
@app.after_request
def apply_cors(response):
    origin = request.headers.get('Origin')
    if origin == ALLOWED_ORIGIN:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '86400'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
