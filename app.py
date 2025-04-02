from flask import Flask, request, jsonify
import pdfplumber
import re
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VALID_VAT_TERMS = {"Zero Rated", "Not Taxable", "Not Applicable"}
skipped_files = []  # List to store skipped file names
CONSIGNEE_NAME = "D H TRADING GROUP SPC CO"  # Required consignee name

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
            "Non Taxable Amount": 0,
            "Taxable Amount": 0,
            "VAT Value": 0,
            "Total AED": float(total_aed.group(1).replace(",", "")) if total_aed else 0
        }

        # Extract charge description details
        vat_entries = set()
        lines = text.split("\n")
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
        invoice_details["Taxable Amount"] = 0
        invoice_details["VAT Value"] = 0

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


def extract_invoice_data1(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

        # Check if the required consignee name is in the text
        if CONSIGNEE_NAME not in text:
            skipped_files.append(os.path.basename(pdf_path))
            return None  # Skip this file

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
            "Consignee Name": CONSIGNEE_NAME,
            "Non Taxable Amount": 0,
            "Taxable Amount": 0,
            "VAT Value": 0,
            "Total AED": float(total_aed.group(1).replace(",", "")) if total_aed else 0
        }

        # Extract charge description details
        vat_entries = set()
        lines = text.split("\n")
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
        invoice_details["Taxable Amount"] = 0
        invoice_details["VAT Value"] = 0

        return invoice_details

    except Exception as e:
        print(f"Error processing {os.path.basename(pdf_path)}: {str(e)}")  # Log error in console
        return None  # Skip this file

@app.route("/upload1", methods=["POST"])
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
        extracted_data = extract_invoice_data1(file_path)

        if extracted_data:  # Only add if it's not skipped
            results.append(extracted_data)

    # Print skipped files in a structured format
    if skipped_files:
        print("\n===== Skipped Files =====")
        for skipped in skipped_files:
            print(skipped)
        print("========================\n")

    return jsonify(results)

def extract_text_with_line_numbers2(pdf_path):
    """ Extracts text from PDF while numbering lines."""
    extracted_lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            line_number = 1
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split("\n")
                    for line in lines:
                        extracted_lines.append(f"{line_number}: {line.strip()}")
                        line_number += 1
        return extracted_lines
    except Exception as e:
        print(f"Error extracting text from {os.path.basename(pdf_path)}: {str(e)}")
        return None


def extract_invoice_data2(pdf_path):
    """ Extracts invoice details and ensures consignee is correct."""
    try:
        lines = extract_text_with_line_numbers2(pdf_path)
        print("\n===== Extracted Text =====")
        print("\n".join(lines))  # This will print extracted text
        print("========================\n")
        if not lines:
            return None

        # Extract invoice number
        invoice_no = next((re.search(r"(INVOICE NUMBER|CREDIT NOTE NUMBER)\s*([\w-]+)", line, re.IGNORECASE).group(2)
                           for line in lines if re.search(r"(INVOICE NUMBER|CREDIT NOTE NUMBER)", line, re.IGNORECASE)), "N/A")

        # Extract invoice date
        invoice_date = next((re.search(r"(INVOICE DATE|DATE)\s*([\dA-Za-z-]+)", line, re.IGNORECASE).group(2)
                             for line in lines if re.search(r"(INVOICE DATE|DATE)", line, re.IGNORECASE)), "N/A")

        # Extract consignee name
        consignee_name = next((re.search(r"CONSIGNEE\s*(.+)", line, re.IGNORECASE).group(1).strip()
                               for line in lines if "CONSIGNEE" in line), "N/A")

        # Extract VAT, subtotal, and total
        vat_value = sum([float(match.group(1).replace(",", ""))
                         for line in lines if (match := re.search(r"VAT\s*([\d.,]+)", line))], 0)

        subtotal = next((float(re.search(r"SUBTOTAL\s*([\d.,]+)", line).group(1).replace(",", ""))
                         for line in lines if "SUBTOTAL" in line), 0)

        total_aed = next((float(re.search(r"TOTAL AED\s*([\d.,]+)", line).group(1).replace(",", ""))
                          for line in lines if "TOTAL AED" in line), 0)

        # Extract charge details
        non_taxable = 0
        taxable = 0
        vat_entries = set()

        relevant_section = False
        for line in lines:
            if "CHARGE DESCRIPTION" in line:
                relevant_section = True
                continue
            if "TOTAL CHARGES" in line:
                relevant_section = False

            if relevant_section:
                match = re.search(r"(\d+): (.+?)\s+((?:Zero Rated|Not Taxable|Not Applicable|5%=\d+\.\d+))?\s+([\d.,]+)\s+([\d.,]+)", line)
                if match:
                    vat_status = match.group(3) if match.group(3) else "Taxable"
                    charge_value = float(match.group(5).replace(",", ""))
                    vat_entries.add(vat_status)

                    if vat_status in VALID_NON_TAXABLE_TERMS:
                        non_taxable += charge_value
                    else:
                        taxable += charge_value

        file_name = os.path.basename(pdf_path)
        is_tax_invoice = "TAX INVOICE" in file_name.upper()

        # Step 1: Check if invoice qualifies based on VAT entries
        if not is_tax_invoice and vat_entries and vat_entries.issubset(VALID_NON_TAXABLE_TERMS):
            skipped_files.append(file_name)
            return None  # Skip due to non-taxable status

        # Step 2: Check if the consignee name matches
        if "D H TRADING GROUP SPC CO" not in consignee_name:
            skipped_files.append(file_name)
            return None  # Skip due to incorrect consignee

        # Return extracted data
        return {
            "Invoice No": invoice_no,
            "Invoice Date": invoice_date,
            "Consignee Name": consignee_name,
            "VAT Value": vat_value,
            "Non Taxable Amount": non_taxable,
            "Taxable Amount": taxable,
            "Total AED": total_aed
        }

    except Exception as e:
        print(f"Error processing {os.path.basename(pdf_path)}: {str(e)}")
        return None


@app.route("/upload2", methods=["POST"])
def upload_file():
    global skipped_files
    skipped_files = []

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    results = []
    for file in request.files.getlist("file"):
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        extracted_data = extract_invoice_data2(file_path)
        if extracted_data:
            results.append(extracted_data)

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
