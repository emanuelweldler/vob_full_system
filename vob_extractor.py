import os
import re
import sqlite3
import PyPDF2
from datetime import datetime
from pathlib import Path


def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                text += page_text
            return text
    except Exception:
        return None


def extract_field(text, pattern, default="NOT FOUND", multiline=False):
    """Extract a field using regex pattern."""
    flags = re.IGNORECASE
    if multiline:
        flags |= re.DOTALL
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else default


def extract_financial_field(text, pattern):
    """Extract financial fields (deductible/OOP) with special handling for None/0."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if (
            value.upper()
            in [
                "NONE",
                "N/A",
                "NA",
                "NO IND DED",
                "NO FAM DED",
                "NO IND OOP",
                "NO FAM OOP",
            ]
            or value.replace("$", "").replace(",", "").strip() == "0"
        ):
            return "0"
        return value
    return "NOT FOUND"


def parse_vob(pdf_path):
    """Parse a VOB PDF and extract required fields."""
    filename = os.path.basename(pdf_path)
    text = extract_text_from_pdf(pdf_path)

    if text is None:
        return None

    # Extract facility name (from filename or document)
    facility_match = re.search(r"VOB Form - (.*?) -", filename)
    facility = (
        facility_match.group(1).strip()
        if facility_match
        else extract_field(text, r"Facility Name\s+(.+?)(?:\n|$)")
    )

    # Determine In/Out of Network
    upper_text = text.upper()
    if "IN NETWORK" in upper_text or "IN-NETWORK" in upper_text:
        network_status = "IN NETWORK"
    elif "OUT OF NETWORK" in upper_text or "OUT-OF-NETWORK" in upper_text:
        network_status = "OUT OF NETWORK"
    else:
        network_status = "NOT FOUND"

    # Extract insurance name - handle multi-line insurance names
    insurance_match = re.search(
        r"Insurance Name\s+(.*?)\s+If OTHER", text, re.IGNORECASE | re.DOTALL
    )
    if insurance_match:
        insurance_name = " ".join(insurance_match.group(1).split())
    else:
        insurance_name = "NOT FOUND"

    # Extract insurance ID
    insurance_id = extract_field(text, r"Insurance ID #\s+(.+?)(?:\s+GROUP|$)")

    # Extract group number
    group_number = extract_field(text, r"GROUP #\s+(.+?)(?:\n|$)")

    # Extract all required fields matching your database schema
    data = {
        "facility_name": facility,
        "insurance_name_raw": insurance_name,
        "payer_canonical": insurance_name,  # You may want to map this to canonical names later
        "insurance_id": insurance_id,
        "insurance_id_clean": insurance_id,  # You may want to add cleaning logic later
        "group_number": group_number,
        "group_number_clean": group_number,  # You may want to add cleaning logic later
        "in_out_network": network_status,
        "deductible_individual": extract_financial_field(
            text, r"Individual Deductible\s+([0-9,]+|NONE|N/A|NO IND DED|\$?0)"
        ),
        "oop_individual": extract_financial_field(
            text, r"Individual Out Of Pocket\s+([0-9,]+|NONE|N/A|NO IND OOP|\$?0)"
        ),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": filename,
        "first_name": extract_field(
            text, r"Patient First Name\s+(.+?)(?:\s+Patient Last Name|$)"
        ),
        "last_name": extract_field(text, r"Patient Last Name\s+(.+?)(?:\n|$)"),
        "exchange_or_employer": extract_field(
            text, r"Exchange or Employer\?\s+(.+?)(?:\s+Employer Name|$)"
        ),
        "employer_name": extract_field(text, r"Employer Name\s+(.+?)(?:\n|$)"),
        "self_or_commercial_funded": extract_field(
            text, r"Self Funded or Commerical\?\s+(.+?)(?:\n|$)"
        ),
        "family_deductible": extract_financial_field(
            text, r"Family Deductible\s+([0-9,]+|NONE|N/A|NO FAM DED|\$?0)"
        ),
        "oop_family": extract_financial_field(
            text, r"Family Out Of Pocket\s+([0-9,]+|NONE|N/A|NO FAM OOP|\$?0)"
        ),
        "dob": extract_field(text, r"DOB\s+(\d+/\d+/\d+)")
    }

    return data


def insert_vob_data(conn, data):
    """Insert VOB data into the vob_records table."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vob_records (
            facility_name, insurance_name_raw, payer_canonical, insurance_id,
            insurance_id_clean, group_number, group_number_clean, in_out_network,
            deductible_individual, oop_individual, created_at, source_file,
            first_name, last_name, exchange_or_employer, employer_name,
            self_or_commercial_funded, family_deductible, oop_family, dob
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["facility_name"],
        data["insurance_name_raw"],
        data["payer_canonical"],
        data["insurance_id"],
        data["insurance_id_clean"],
        data["group_number"],
        data["group_number_clean"],
        data["in_out_network"],
        data["deductible_individual"],
        data["oop_individual"],
        data["created_at"],
        data["source_file"],
        data["first_name"],
        data["last_name"],
        data["exchange_or_employer"],
        data["employer_name"],
        data["self_or_commercial_funded"],
        data["family_deductible"],
        data["oop_family"],
        data["dob"]
    ))
    conn.commit()


def process_vobs(folder_path, db_path):
    """Process VOB PDFs and insert directly into database."""
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Find all VOB PDFs
    root = Path(folder_path)
    pdf_files = [
        p
        for p in root.rglob("*.pdf")
        if p.is_file()
        and p.name.lower().startswith("vob form -")
        and "insurance cards" not in str(p).lower()
    ]

    if not pdf_files:
        print(f"No VOB PDF files found in {folder_path}")
        conn.close()
        return

    print(f"Found {len(pdf_files)} VOB PDF files. Processing...")

    successful = 0
    failed = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"Processing {i}/{len(pdf_files)}: {pdf_path.name}")

        data = parse_vob(str(pdf_path))

        if data is None:
            print(f"  ✗ Failed to read PDF")
            failed += 1
        else:
            try:
                insert_vob_data(conn, data)
                print(f"  ✓ Inserted into database")
                
                # Delete the PDF after successful processing
                try:
                    os.remove(pdf_path)
                    print(f"  ✓ Deleted PDF file")
                except Exception as e:
                    print(f"  ⚠ Warning: Could not delete file: {e}")
                
                successful += 1
            except Exception as e:
                print(f"  ✗ Database error: {e}")
                failed += 1

    conn.close()

    print("\n" + "=" * 60)
    print(f"Processing complete!")
    print(f"  ✓ Successfully processed: {successful}")
    print(f"  ✗ Failed: {failed}")
    print("=" * 60)


def main():
    # Configure these paths
    folder_path = r"C:\Users\tvsho\OneDrive - Midwest Detox\VOB Folder - All"
    db_path = r"C:\Data\VOB_DB\vob.db"
    
    print("=" * 60)
    print("VOB DATA EXTRACTOR - SQLITE EDITION")
    print("=" * 60)
    print(f"Source folder: {folder_path}")
    print(f"Database: {db_path}")
    print("=" * 60)

    process_vobs(folder_path, db_path)


if __name__ == "__main__":
    main()