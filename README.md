# Excel Bulk Update Tool

A streamlined Streamlit application for automatic bulk updating of databases from Excel files via drag-and-drop.

## Features

- 🚀 **Auto-Update**: Drag and drop Excel files to automatically update the database
- 📤 **Simple Upload**: Just drop your file - no extra buttons needed
- 📋 **Required Columns**: Company, Name, Surname, Email, Position, Phone
- 📊 **Data Preview**: View and search your database records
- 🔄 **Update Modes**: Replace (overwrite) or Append (add new) records
- ✅ **SQL Storage**: Data stored in SQLite database for easy querying

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

Or use the provided batch file:
```bash
run_app.bat
```

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. The application will open in your browser automatically (usually at http://localhost:8501).

3. **How to Use**:
   - **Upload Tab**: Drag and drop your Excel file (.xlsx or .xls)
   - The file will automatically be processed and updated to the database
   - If multiple sheets exist, select which sheet to use
   - Choose update mode (Replace or Append) in the sidebar
   - **View Database Tab**: Browse, search, and download your stored data

## Excel File Requirements

Your Excel file must contain these columns (case-insensitive):
- **Company**
- **Name**
- **Surname**
- **Email**
- **Position**
- **Phone**

The tool will automatically extract these columns in the correct order, ignoring any other columns in your Excel file.

## Database

- **Database name**: `FW_data_base.db` (SQLite)
- **Table name**: `contacts_data`
- The table is automatically created on first upload
- All data is stored in SQL format for easy querying and management

## Update Modes

- **Replace**: Overwrites all existing data in the database
- **Append**: Adds new records to existing data (keeps old records)

## Notes

- The tool only uses the 6 required columns listed above
- Other columns in your Excel file will be ignored
- The database is created automatically if it doesn't exist
- Data is stored as strings for maximum compatibility

