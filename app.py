from flask import Flask, request, jsonify
import pdfplumber
import re
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VALID_VAT_TERMS = {"Zero Rated", "Not Taxable", "Not Applicable"}
CONSIGNEE_NAME = "D H TRADING GROUP SPC CO"  # Required consignee name

def extract_text_from_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    except Exception as e:
        print(f"Error reading {os.path.basename(pdf_path)}: {str(e)}")
        return None

def extract_invoice_data(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None

    invoice_no = re.search(r"INVOICE NUMBER\s*([\w-]+)", text) or re.search(r"CREDIT NOTE NUMBER\s*([\w-]+)", text)
    invoice_date = re.search(r"INVOICE DATE\s*([\dA-Za-z-]+)", text) or re.search(r"DATE\s*([\dA-Za-z-]+)", text)
    subtotal = re.search(r"SUBTOTAL\s*([\d.,]+)", text)
    total_aed = re.search(r"TOTAL AED\s*([\d.,]+)", text)
    
    vat_entries = set()
    for line in text.split("\n"):
        match = re.search(r"(.+?)\s+(Zero Rated|Not Taxable|Not Applicable|\d+%=\d+\.\d+)?\s+([\d.,]+)\s+([\d.,]+)", line)
        if match:
            vat_entries.add(match.group(2) if match.group(2) else "Taxable")
    
    if not vat_entries.issubset(VALID_VAT_TERMS):
        return None
    
    return {
        "Invoice No": invoice_no.group(1) if invoice_no else "N/A",
        "Invoice Date": invoice_date.group(1) if invoice_date else "N/A",
        "Non Taxable Amount": float(subtotal.group(1).replace(",", "")) if subtotal else 0,
        "Taxable Amount": 0,
        "VAT Value": 0,
        "Total AED": float(total_aed.group(1).replace(",", "")) if total_aed else 0
    }

def extract_invoice_data1(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    if not text or CONSIGNEE_NAME not in text:
        return None
    
    data = extract_invoice_data(pdf_path)
    if data:
        data["Consignee Name"] = CONSIGNEE_NAME
    return data

def extract_invoice_data2(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None
    
    lines = text.split("\n")
    vat_entries = set()
    non_taxable, taxable, vat_value = 0, 0, 0
    found_charges = False
    
    for line in lines:
        if "CHARGE DESCRIPTION" in line:
            found_charges = True
            continue
        if found_charges:
            match = re.search(r"(.+?)\s+(Zero Rated|Not Taxable|Not Applicable|\d+%=\d+\.\d+)?\s+([\d.,]+)\s+([\d.,]+)", line)
            if match:
                vat_status = match.group(2) if match.group(2) else "Taxable"
                amount = float(match.group(4).replace(",", ""))
                vat_entries.add(vat_status)
                if vat_status in VALID_VAT_TERMS:
                    non_taxable += amount
                else:
                    taxable += amount
    
    if "D H TRADING GROUP SPC CO" not in text or not vat_entries.issubset(VALID_VAT_TERMS):
        return None
    
    invoice_no = re.search(r"INVOICE NUMBER\s*([\w-]+)", text) or re.search(r"CREDIT NOTE NUMBER\s*([\w-]+)", text)
    invoice_date = re.search(r"INVOICE DATE\s*([\dA-Za-z-]+)", text) or re.search(r"DATE\s*([\dA-Za-z-]+)", text)
    subtotal = re.search(r"SUBTOTAL\s*([\d.,]+)", text)
    total_aed = re.search(r"TOTAL AED\s*([\d.,]+)", text)
    
    return {
        "Invoice No": invoice_no.group(1) if invoice_no else "N/A",
        "Invoice Date": invoice_date.group(1) if invoice_date else "N/A",
        "Consignee Name": "D H TRADING GROUP SPC CO",
        "VAT Value": vat_value,
        "Non Taxable Amount": non_taxable,
        "Taxable Amount": taxable,
        "Total AED": float(total_aed.group(1).replace(",", "")) if total_aed else 0
    }

def process_upload(request, extraction_function):
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    results, skipped_files = [], []
    for file in request.files.getlist("file"):
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        extracted_data = extraction_function(file_path)
        if extracted_data:
            results.append(extracted_data)
        else:
            skipped_files.append(file.filename)
    
    return jsonify({"processed": results, "skipped": skipped_files})

@app.route("/upload", methods=["POST"])
def upload():
    return process_upload(request, extract_invoice_data)

@app.route("/upload1", methods=["POST"])
def upload1():
    return process_upload(request, extract_invoice_data1)

@app.route("/upload2", methods=["POST"])
def upload2():
    return process_upload(request, extract_invoice_data2)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "UP"}), 200

if __name__ == "__main__":
    app.run(debug=True)
