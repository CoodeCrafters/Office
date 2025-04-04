from flask import Flask, request, jsonify
import pdfplumber
import re
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VALID_VAT_TERMS = {"Zero Rated", "Not Taxable", "Not Applicable"}
skipped_files = []  # List to store skipped file names

# Predefined base names for matching
BASE_NAMES = ["D H TRADING GROUP SPC CO", "DUBAI HOLDING GROUP - INDITEX PROJECT", "INDITEX S.A."]

def extract_invoice_data(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

        # Extract Invoice or Credit Note Number
        invoice_no = re.search(r"INVOICE NUMBER\s*([\w-]+)", text) or re.search(r"CREDIT NOTE NUMBER\s*([\w-]+)", text)
        
        # Extract Invoice or Credit Note Date
        invoice_date = re.search(r"INVOICE DATE\s*([\dA-Za-z-]+)", text) or re.search(r"DATE\s*([\dA-Za-z-]+)", text)

        # Extract Subtotal
        subtotal = re.search(r"SUBTOTAL\s*([\d.,]+)", text)

        # Extract Total AED
        total_aed = re.search(r"TOTAL AED\s*([\d.,]+)", text)

        # Initialize Invoice Data
        invoice_details = {
            "Invoice No": invoice_no.group(1) if invoice_no else "N/A",
            "Invoice Date": invoice_date.group(1) if invoice_date else "N/A",
            "Shipper": "N/A",
            "Consignee": "N/A",
            "Non Taxable Amount": 0,
            "Taxable Amount": 0,
            "VAT Value": 0,
            "Total AED": float(total_aed.group(1).replace(",", "")) if total_aed else 0
        }

        # Extract SHIPPER and CONSIGNEE names
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "SHIPPER" in line and "CONSIGNEE" in line:
                if i + 1 < len(lines):  # Ensure the next line exists
                    names_line = lines[i + 1]

                    # Debugging: Print the extracted lines
                    print("\n===== Raw SHIPPER CONSIGNEE Line =====")
                    print(f"Line 1: {line}")
                    print(f"Line 2: {names_line}")
                    print("====================================\n")

                    # Find the first base name from right to left
                    matched_base = None
                    for base in BASE_NAMES[::-1]:  # Check from right to left
                        if base in names_line:
                            matched_base = base
                            break

                    if matched_base:
                        invoice_details["Consignee"] = matched_base
                        invoice_details["Shipper"] = names_line.replace(matched_base, "").strip()
                    else:
                        invoice_details["Shipper"] = names_line.strip()  # Fallback if no match

                break  # Stop after processing first SHIPPER/CONSIGNEE block

        # Extract charge description details
        vat_entries = set()
        found_charge_table = False

        for line in lines:
            if "CHARGE DESCRIPTION" in line:
                found_charge_table = True
                continue

            if found_charge_table:
                match = re.search(r"(.+?)\s+(Zero Rated|Not Taxable|Not Applicable|\d+%=\d+\.\d+)?\s+([\d.,]+)\s+([\d.,]+)", line)
                if match:
                    vat_status = match.group(2) if match.group(2) else "Taxable"
                    vat_entries.add(vat_status)

        # If VAT entries contain disallowed terms, skip the file and log
        if not vat_entries.issubset(VALID_VAT_TERMS):
            skipped_files.append(os.path.basename(pdf_path))
            return None  # Skip this file

        # If all VAT entries are valid, use Subtotal as Non-Taxable Amount
        subtotal_value = float(subtotal.group(1).replace(",", "")) if subtotal else 0
        invoice_details["Non Taxable Amount"] = subtotal_value

        # Print final extracted data
        print("\n===== Final Extracted Data =====")
        print(invoice_details)
        print("================================\n")

        return invoice_details

    except Exception as e:
        print(f"Error processing {os.path.basename(pdf_path)}: {str(e)}")  # Log error in console
        return None  # Skip this file

@app.route("/upload", methods=["POST"])
def upload_file():
    global skipped_files  # Reset the skipped files list for each request
    skipped_files = []

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded_files = request.files.getlist("file")
    results = []

    for file in uploaded_files:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        extracted_data = extract_invoice_data(file_path)

        if extracted_data:  # Only add if it's not skipped
            results.append(extracted_data)

    # Print skipped files in a structured format
    if skipped_files:
        print("\n===== Skipped Files =====")
        for skipped in skipped_files:
            print(skipped)
        print("========================\n")

    return jsonify(results)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "UP"}), 200

if __name__ == "__main__":
    app.run(debug=True)
