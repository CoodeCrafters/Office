from flask import Flask, request, jsonify
import pandas as pd
from io import BytesIO, StringIO
from flask_cors import CORS
import re
import time
import os
from datetime import datetime

app = Flask(__name__)

# Enable CORS for all routes from your GitHub Pages domain
CORS(app, resources={
    r"/*": {  # This will apply to all routes
        "origins": ["https://coodecrafters.github.io"],
        "methods": ["GET", "POST", "OPTIONS"],  # Add OPTIONS for preflight
        "allow_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# Store the last response time
last_response_time = 0
response_interval = 210  # 3.5 minutes in seconds

@app.route('/keepalive', methods=['GET', 'OPTIONS'])
def keepalive():
    global last_response_time
    
    # Handle OPTIONS preflight request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'preflight'})
        response.headers.add('Access-Control-Allow-Origin', 'https://coodecrafters.github.io')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response
    
    current_time = time.time()
    time_since_last = current_time - last_response_time
    
    if time_since_last >= response_interval:
        last_response_time = current_time
        response = jsonify({
            "status": "active",
            "message": "Server keepalive ping",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "next_ping_in": f"{response_interval} seconds"
        })
    else:
        response = jsonify({
            "status": "active",
            "message": "Server is alive",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "seconds_until_next_ping": int(response_interval - time_since_last)
        })
    
    # Add CORS headers to the actual response
    response.headers.add('Access-Control-Allow-Origin', 'https://coodecrafters.github.io')
    return response

# Mapping of brand names to merchant IDs
BRAND_MAPPING = {
    "SFERA": "1000020410",
    "WOMEN SECRET": "1000027886",
    "STRADIVARIUS AL MARYAH": "1000058592",
    "SPRINGFIELD": "1000239457",
    "ZARA HOME": "1000175313",
    "LEFTIES": "1000175297"
}

def extract_date_from_filename(filename):
    """Extract date from filename in DD.MM.YY format"""
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
        # Handle OPTIONS preflight request
        if request.method == 'OPTIONS':
            response = jsonify({'status': 'preflight'})
            response.headers.add('Access-Control-Allow-Origin', 'https://coodecrafters.github.io')
            response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
            return response
        
        # Check if file was uploaded
        if 'excelFile' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['excelFile']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        # Extract date from filename
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
                brand_name = str(df.iloc[header_row, 13]).strip().upper()  # Column N (index 13)
                
                if brand_name in BRAND_MAPPING:
                    merchant_id = BRAND_MAPPING[brand_name]
                    outlet_name = str(df.iloc[header_row, 14]).strip()  # Column O (index 14)
                    
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
        response.headers.add('Access-Control-Allow-Origin', 'https://coodecrafters.github.io')
        return response
    
    except Exception as e:
        response = jsonify({"error": str(e)})
        response.headers.add('Access-Control-Allow-Origin', 'https://coodecrafters.github.io')
        return response, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
