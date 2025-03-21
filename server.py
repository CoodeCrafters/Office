from flask import Flask, request, jsonify
import pdfplumber
import re
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VALID_NON_TAXABLE_TERMS = {"Zero Rated", "Not Taxable", "Not Applicable"}
skipped_files = []  # Stores skipped filenames for Case 1

def extract_text_with_line_numbers(pdf_path):
    """ Extracts text from PDF while numbering lines for better structure. """
    extracted_lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            line_number = 1  # Start numbering from 1
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split("\n")
                    for line in lines:
                        formatted_line = f"{line_number}: {line.strip()}"
                        extracted_lines.append(formatted_line)  # Add line numbers
                        line_number += 1

        return extracted_lines
    except Exception as e:
        print(f"Error extracting text from {os.path.basename(pdf_path)}: {str(e)}")
        return None

def extract_invoice_data(pdf_path):
    """ Extracts invoice details and supports Credit Notes correctly. """
    try:
        lines = extract_text_with_line_numbers(pdf_path)
        if not lines:
            return None

        # Extract Invoice/Credit Note Number
        invoice_no = next((re.search(r"(INVOICE NUMBER|CREDIT NOTE NUMBER)\s*([\w-]+)", line, re.IGNORECASE).group(2) 
                           for line in lines if re.search(r"(INVOICE NUMBER|CREDIT NOTE NUMBER)", line, re.IGNORECASE)), "N/A")

        # Extract Invoice Date or General Date
        invoice_date = next((re.search(r"(INVOICE DATE|DATE)\s*([\dA-Za-z-]+)", line, re.IGNORECASE).group(2) 
                             for line in lines if re.search(r"(INVOICE DATE|DATE)", line, re.IGNORECASE)), "N/A")

        # Extract VAT, Subtotal, and Total AED
        vat_value = sum([float(match.group(1).replace(",", "")) 
                         for line in lines if (match := re.search(r"VAT\s*([\d.,]+)", line))], 0)
        subtotal = next((float(re.search(r"SUBTOTAL\s*([\d.,]+)", line).group(1).replace(",", "")) 
                         for line in lines if "SUBTOTAL" in line), 0)
        total_aed = next((float(re.search(r"TOTAL AED\s*([\d.,]+)", line).group(1).replace(",", "")) 
                          for line in lines if "TOTAL AED" in line), 0)

        # Initialize values
        non_taxable = 0
        taxable = 0
        found_charge_table = False
        relevant_section = False  # To extract only the required part
        vat_entries = set()  # Stores all VAT statuses found

        for line in lines:
            if "CHARGE DESCRIPTION" in line:
                found_charge_table = True
                relevant_section = True  # Start extracting from this line
                continue
            if "TOTAL CHARGES" in line:
                relevant_section = False  # Stop extracting

            if relevant_section:
                # Match taxable and non-taxable charges
                match = re.search(r"(\d+): (.+?)\s+((?:Zero Rated|Not Taxable|Not Applicable|5%=\d+\.\d+))?\s+([\d.,]+)\s+([\d.,]+)", line)
                if match:
                    vat_status = match.group(3) if match.group(3) else "Taxable"
                    charge_value = float(match.group(5).replace(",", ""))  # Get last numeric value

                    vat_entries.add(vat_status)  # Track VAT types found

                    if vat_status in VALID_NON_TAXABLE_TERMS:
                        non_taxable += charge_value  # Sum only non-taxable rows
                    else:
                        taxable += charge_value  # ✅ Properly sum taxable charges

        # **NEW RULE: Do not skip "TAX INVOICE" files**
        file_name = os.path.basename(pdf_path)
        is_tax_invoice = "TAX INVOICE" in file_name.upper()

        # Skip Case 1 invoices (if all VAT entries are "Zero Rated", "Not Applicable", or "Not Taxable"),
        # BUT KEEP "TAX INVOICE" FILES!
        if not is_tax_invoice and vat_entries and vat_entries.issubset(VALID_NON_TAXABLE_TERMS):
            skipped_files.append(file_name)
            return None  # Skip this file

        # Invoice details dictionary
        invoice_details = {
            "Document No": invoice_no,
            "Document Date": invoice_date,
            "VAT Value": vat_value,
            "Non Taxable Amount": non_taxable,
            "Taxable Amount": taxable,
            "Total AED": total_aed
        }

        return invoice_details

    except Exception as e:
        print(f"Error processing {os.path.basename(pdf_path)}: {str(e)}")
        return None  # Skip this file

@app.route("/upload", methods=["POST"])
def upload_file():
    global skipped_files  # Reset skipped files list for each request
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

    # Print skipped files
    if skipped_files:
        print("\n===== Skipped Files (Case 1) =====")
        for skipped in skipped_files:
            print(skipped)
        print("========================\n")

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
