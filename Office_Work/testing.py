from flask import Flask, request, jsonify
import pandas as pd
from io import BytesIO, StringIO
from flask_cors import CORS
import re
from datetime import datetime

app = Flask(__name__)

# Enable CORS
CORS(app, resources={
    r"/retrieve*": {
        "origins": ["http://127.0.0.1:5500", "http://localhost:5500"],
        "methods": ["POST"],
        "allow_headers": ["Content-Type"]
    }
})

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

@app.route('/retrieve', methods=['POST'])
def retrieve_data():
    try:
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
        
        return jsonify({
            "status": "success",
            "date": file_date,
            "data": list(results.values())
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
