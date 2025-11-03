import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from datetime import datetime
import os
import io
import tempfile
import time

# Page configuration
st.set_page_config(
    page_title="FW Data Base - Excel Bulk Update Tool",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'db_updated' not in st.session_state:
    st.session_state.db_updated = False
if 'last_file' not in st.session_state:
    st.session_state.last_file = None

# Database connection string (SQLite)
DB_NAME = "FW_data_base.db"
DATABASE_URL = f"sqlite:///{DB_NAME}"

# Required columns in order
REQUIRED_COLUMNS = ['Company', 'Name', 'Surname', 'Email', 'Position', 'Phone']
TABLE_NAME = "contacts_data"

def get_engine():
    """Create database engine connection"""
    try:
        return create_engine(DATABASE_URL, echo=False)
    except Exception as e:
        st.error(f"❌ Database connection error: {str(e)}")
        return None

def validate_columns(df):
    """Validate that DataFrame has all required columns"""
    # Normalize column names - remove all whitespace, convert to lowercase for comparison
    df_columns_normalized = {}
    for df_col in df.columns:
        # Strip and normalize the column name
        col_str = str(df_col).strip()
        normalized = col_str.lower().replace(' ', '').replace('_', '').replace('-', '')
        df_columns_normalized[normalized] = df_col
    
    missing_cols = []
    column_mapping = {}
    
    for req_col in REQUIRED_COLUMNS:
        found = False
        req_col_normalized = req_col.lower().replace(' ', '').replace('_', '').replace('-', '')
        
        # Try exact match first (case-insensitive, whitespace-insensitive)
        if req_col_normalized in df_columns_normalized:
            column_mapping[req_col] = df_columns_normalized[req_col_normalized]
            found = True
        else:
            # Try direct comparison with original column names (case-insensitive)
            for df_col in df.columns:
                df_col_clean = str(df_col).strip()
                if df_col_clean.lower() == req_col.lower():
                    column_mapping[req_col] = df_col
                    found = True
                    break
        
        if not found:
            missing_cols.append(req_col)
    
    return len(missing_cols) == 0, missing_cols, column_mapping

def extract_required_columns(df, column_mapping):
    """Extract and reorder DataFrame to have required columns in correct order"""
    result_df = pd.DataFrame()
    
    for req_col in REQUIRED_COLUMNS:
        if req_col in column_mapping:
            df_col = column_mapping[req_col]
            result_df[req_col] = df[df_col]
        else:
            result_df[req_col] = None
    
    # Convert to string to avoid serialization issues
    for col in result_df.columns:
        result_df[col] = result_df[col].astype(str).replace('nan', '')
    
    return result_df

def validate_file_format(uploaded_file):
    """Validate file format and return file extension and validation status"""
    # Reset file pointer
    uploaded_file.seek(0)
    
    # Check if file is empty
    if uploaded_file.size == 0:
        return False, "Empty", "Uploaded file is empty!"
    
    # Get file extension
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    # Validate file type
    if file_extension not in ['xlsx', 'xls']:
        return False, file_extension, f"Invalid file type '{file_extension}'. Please upload .xlsx or .xls files."
    
    # Determine engine
    engine_name = 'xlrd' if file_extension == 'xls' else 'openpyxl'
    
    return True, file_extension, engine_name

def read_excel_file(tmp_file_path, file_extension, engine_name):
    """Read Excel file and return sheet names - temp file should already exist"""
    excel_file = None
    
    try:
        # Try multiple engines to read file
        engines_to_try = []
        if file_extension == 'xlsx':
            engines_to_try = [
                ('auto-detect', None),
                ('openpyxl', 'openpyxl'),
                ('xlrd', 'xlrd')
            ]
        else:  # .xls
            engines_to_try = [
                ('auto-detect', None),
                ('xlrd', 'xlrd'),
                ('openpyxl', 'openpyxl')
            ]
        
        last_error = None
        successful_engine = None
        sheet_names = None
        
        for engine_display, engine_to_try in engines_to_try:
            try:
                if excel_file:
                    try:
                        excel_file.close()
                    except:
                        pass
                
                # Try reading with this engine
                if engine_to_try is None:
                    excel_file = pd.ExcelFile(tmp_file_path)
                else:
                    excel_file = pd.ExcelFile(tmp_file_path, engine=engine_to_try)
                
                sheet_names = excel_file.sheet_names
                successful_engine = engine_to_try if engine_to_try else 'auto-detect'
                engine_name = successful_engine if successful_engine != 'auto-detect' else 'openpyxl'
                excel_file.close()
                excel_file = None
                break
                
            except Exception as e:
                last_error = str(e)
                error_lower = str(e).lower()
                
                # Check if file might be encrypted
                is_encrypted = any(keyword in error_lower for keyword in [
                    'password', 'encrypted', 'protected', 
                    'ole2', 'compound document',
                    'permission denied', 'access denied',
                    'locked', 'security'
                ])
                
                if engine_display == engines_to_try[-1][0]:
                    # Last engine failed
                    if is_encrypted or 'ole2' in error_lower or 'compound document' in error_lower:
                        error_msg = "🔒 File is Encrypted or Password-Protected"
                        details = "⚠️ The document appears to be encrypted or is an internal Excel file format."
                        return False, None, None, error_msg, details
                    else:
                        error_msg = f"❌ Error reading Excel file: All methods failed"
                        details = f"Last error ({engine_display}): {last_error}"
                        return False, None, None, error_msg, details
        
        if not sheet_names:
            return False, None, None, "❌ Could not read file with any method", ""
        
        return True, sheet_names, engine_name, None, None
        
    except Exception as e:
        if excel_file:
            try:
                excel_file.close()
            except:
                pass
        return False, None, None, f"Error reading file: {str(e)}", ""

def process_sheet(tmp_file_path, sheet_name, engine_name):
    """Process a single sheet: read, validate columns, and return processed DataFrame"""
    try:
        # Read the sheet
        df = pd.read_excel(tmp_file_path, sheet_name=sheet_name, engine=engine_name, header=0)
        
        # Validate columns
        is_valid, missing_cols, column_mapping = validate_columns(df)
        
        if not is_valid:
            return False, None, f"Missing required columns: {', '.join(missing_cols)}", missing_cols, column_mapping
        
        # Extract required columns
        df_processed = extract_required_columns(df, column_mapping)
        
        return True, df_processed, None, None, column_mapping
        
    except Exception as e:
        return False, None, f"Error reading sheet '{sheet_name}': {str(e)}", None, None

def load_data_from_db(engine):
    """Load all data from database"""
    try:
        inspector = inspect(engine)
        if TABLE_NAME in inspector.get_table_names():
            df = pd.read_sql_table(TABLE_NAME, engine)
            # Convert to string
            for col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '')
            return df
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def update_database(engine, df, update_mode='replace'):
    """Update database with DataFrame and return change details"""
    try:
        # Convert to string
        df_copy = df.copy()
        for col in df_copy.columns:
            df_copy[col] = df_copy[col].astype(str).replace('nan', '')
        
        changes_details = []  # Store change details
        
        # Update database
        if update_mode == 'replace':
            # Smart replace: Update existing rows, add new ones, keep existing ones not in new file
            # Use Email as unique identifier for matching
            inspector = inspect(engine)
            
            if TABLE_NAME in inspector.get_table_names():
                # Load existing data
                existing_df = load_data_from_db(engine)
                
                if len(existing_df) > 0:
                    # Normalize Email for comparison
                    df_copy['_email_key'] = df_copy['Email'].astype(str).str.lower().str.strip()
                    existing_df['_email_key'] = existing_df['Email'].astype(str).str.lower().str.strip()
                    
                    # Create a set of Email addresses from new file
                    new_emails = set(df_copy['_email_key'])
                    existing_emails = set(existing_df['_email_key'])
                    
                    # Find rows to keep (existing rows not in new file)
                    rows_to_keep = existing_df[~existing_df['_email_key'].isin(new_emails)].copy()
                    
                    # Find matching records to update
                    matching_emails = new_emails & existing_emails
                    
                    # Track changes for each updated record
                    for email in matching_emails:
                        old_row = existing_df[existing_df['_email_key'] == email].iloc[0]
                        new_row = df_copy[df_copy['_email_key'] == email].iloc[0]
                        
                        # Compare each column
                        changed_cols = {}
                        for col in REQUIRED_COLUMNS:
                            old_val = str(old_row.get(col, '')).strip()
                            new_val = str(new_row.get(col, '')).strip()
                            if old_val != new_val:
                                changed_cols[col] = {
                                    'old': old_val if old_val else '(empty)',
                                    'new': new_val if new_val else '(empty)'
                                }
                        
                        if changed_cols:
                            # Clean email from HTML tags if any
                            clean_email = email
                            if '<a href' in str(email):
                                import re
                                # Extract email from HTML anchor tag
                                email_match = re.search(r'>(.*?)</a>', str(email))
                                if email_match:
                                    clean_email = email_match.group(1)
                                else:
                                    # Try to extract from href
                                    email_match = re.search(r'mailto:(.*?)[">]', str(email))
                                    if email_match:
                                        clean_email = email_match.group(1)
                            
                            changes_details.append({
                                'email': clean_email,
                                'name': str(new_row.get('Name', '')),
                                'surname': str(new_row.get('Surname', '')),
                                'changed_columns': changed_cols
                            })
                    
                    # Remove temporary key column
                    df_copy = df_copy.drop(columns=['_email_key'])
                    rows_to_keep = rows_to_keep.drop(columns=['_email_key'])
                    
                    # Find rows to update (existing emails in new file) and new rows (new emails)
                    rows_to_add = df_copy.copy()
                    
                    # Combine: keep old rows + new/updated rows
                    if len(rows_to_keep) > 0:
                        final_df = pd.concat([rows_to_keep, rows_to_add], ignore_index=True)
                    else:
                        final_df = rows_to_add
                    
                    # Replace entire table with merged data
                    final_df.to_sql(TABLE_NAME, engine, index=False, if_exists='replace', method='multi')
                    
                    updated_count = len(matching_emails)  # Emails that exist in both
                    new_count = len(new_emails - existing_emails)  # New emails
                    kept_count = len(rows_to_keep)  # Rows kept from old data
                    
                    return True, {
                        'message': f"✅ Successfully updated database! Updated: {updated_count} rows, Added: {new_count} rows, Kept: {kept_count} existing rows.",
                        'updated_count': updated_count,
                        'new_count': new_count,
                        'kept_count': kept_count,
                        'changes': changes_details
                    }
                else:
                    # No existing data, just insert new
                    df_copy.to_sql(TABLE_NAME, engine, index=False, if_exists='replace', method='multi')
                    return True, {
                        'message': f"✅ Successfully added {len(df_copy)} new rows!",
                        'updated_count': 0,
                        'new_count': len(df_copy),
                        'kept_count': 0,
                        'changes': []
                    }
            else:
                # Table doesn't exist, create it
                df_copy.to_sql(TABLE_NAME, engine, index=False, if_exists='replace', method='multi')
                return True, {
                    'message': f"✅ Successfully created table and added {len(df_copy)} rows!",
                    'updated_count': 0,
                    'new_count': len(df_copy),
                    'kept_count': 0,
                    'changes': []
                }
        else:
            # Append mode - add only new rows (skip duplicates based on Email)
            inspector = inspect(engine)
            duplicates_count = 0
            new_rows_count = 0
            
            if TABLE_NAME in inspector.get_table_names():
                # Load existing data to check for duplicates
                existing_df = load_data_from_db(engine)
                
                if len(existing_df) > 0:
                    # Normalize Email for comparison
                    df_copy['_email_key'] = df_copy['Email'].astype(str).str.lower().str.strip()
                    existing_df['_email_key'] = existing_df['Email'].astype(str).str.lower().str.strip()
                    
                    # Find which rows are new (not in existing database)
                    existing_emails = set(existing_df['_email_key'])
                    df_copy['_is_new'] = ~df_copy['_email_key'].isin(existing_emails)
                    
                    # Count duplicates
                    duplicates_count = (~df_copy['_is_new']).sum()
                    new_rows_count = df_copy['_is_new'].sum()
                    
                    # Filter to only new rows (skip duplicates)
                    df_new_only = df_copy[df_copy['_is_new']].copy()
                    
                    # Remove temporary columns
                    df_new_only = df_new_only.drop(columns=['_email_key', '_is_new'])
                    df_copy = df_copy.drop(columns=['_email_key', '_is_new'])
                    
                    if len(df_new_only) > 0:
                        # Add only new rows
                        df_new_only.to_sql(TABLE_NAME, engine, index=False, if_exists='append', method='multi')
                        
                        if duplicates_count > 0:
                            message = f"✅ Successfully appended {new_rows_count} new rows! (Skipped {duplicates_count} duplicate email(s))"
                        else:
                            message = f"✅ Successfully appended {new_rows_count} new rows!"
                        
                        return True, {
                            'message': message,
                            'updated_count': 0,
                            'new_count': new_rows_count,
                            'kept_count': len(existing_df),
                            'duplicates_count': duplicates_count,
                            'changes': []
                        }
                    else:
                        # All rows were duplicates
                        return True, {
                            'message': f"⚠️ All {len(df_copy)} rows already exist in database (duplicate emails). No rows added.",
                            'updated_count': 0,
                            'new_count': 0,
                            'kept_count': len(existing_df),
                            'duplicates_count': duplicates_count,
                            'changes': []
                        }
                else:
                    # No existing data, just insert all
                    df_copy.to_sql(TABLE_NAME, engine, index=False, if_exists='append', method='multi')
                    return True, {
                        'message': f"✅ Successfully appended {len(df_copy)} rows!",
                        'updated_count': 0,
                        'new_count': len(df_copy),
                        'kept_count': 0,
                        'duplicates_count': 0,
                        'changes': []
                    }
            else:
                # Table doesn't exist, create it
                df_copy.to_sql(TABLE_NAME, engine, index=False, if_exists='replace', method='multi')
                return True, {
                    'message': f"✅ Successfully created table and added {len(df_copy)} rows!",
                    'updated_count': 0,
                    'new_count': len(df_copy),
                    'kept_count': 0,
                    'duplicates_count': 0,
                    'changes': []
                }
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_db_stats(engine):
    """Get database statistics"""
    try:
        inspector = inspect(engine)
        if TABLE_NAME in inspector.get_table_names():
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}"))
                count = result.scalar()
            return {'exists': True, 'row_count': count}
        return {'exists': False, 'row_count': 0}
    except:
        return {'exists': False, 'row_count': 0}

def delete_row_from_db(engine, row_data_dict):
    """Delete a row from database based on all column values"""
    try:
        conditions = []
        params = {}
        for idx, (col, val) in enumerate(row_data_dict.items()):
            param_name = f"val_{idx}"
            conditions.append(f'"{col}" = :{param_name}')
            params[param_name] = val
        
        delete_query = f'DELETE FROM {TABLE_NAME} WHERE {" AND ".join(conditions)}'
        
        with engine.connect() as conn:
            conn.execute(text(delete_query), params)
            conn.commit()
        
        return True, "Row deleted successfully!"
    except Exception as e:
        return False, f"Error deleting row: {str(e)}"

def update_row_in_db(engine, old_row_data, new_row_data):
    """Update a row in database"""
    try:
        # Build WHERE clause from old row data
        conditions = []
        params = {}
        for idx, (col, val) in enumerate(old_row_data.items()):
            param_name = f"where_{idx}"
            conditions.append(f'"{col}" = :{param_name}')
            params[param_name] = val
        
        # Build SET clause from new row data
        set_clauses = []
        for idx, (col, val) in enumerate(new_row_data.items()):
            param_name = f"set_{idx}"
            set_clauses.append(f'"{col}" = :{param_name}')
            params[param_name] = val
        
        update_query = f'UPDATE {TABLE_NAME} SET {", ".join(set_clauses)} WHERE {" AND ".join(conditions)}'
        
        with engine.connect() as conn:
            conn.execute(text(update_query), params)
            conn.commit()
        
        return True, "Row updated successfully!"
    except Exception as e:
        return False, f"Error updating row: {str(e)}"

def delete_entire_database(engine):
    """Delete the entire database table"""
    try:
        inspector = inspect(engine)
        if TABLE_NAME in inspector.get_table_names():
            with engine.connect() as conn:
                conn.execute(text(f'DROP TABLE IF EXISTS {TABLE_NAME}'))
                conn.commit()
            return True, "Database table deleted successfully!"
        else:
            return False, "Table does not exist"
    except Exception as e:
        return False, f"Error deleting database: {str(e)}"

def main():
    st.title("📊 Excel Bulk Update Tool - Auto Upload")
    st.markdown("**Drag & Drop Excel file to automatically update the database**")
    st.markdown("---")
    
    # Initialize database connection
    engine = get_engine()
    if not engine:
        st.error("❌ Failed to connect to database!")
        st.stop()
    
    # Sidebar with database info and settings
    with st.sidebar:
        st.header("📊 Database Info")
        stats = get_db_stats(engine)
        
        if stats['exists']:
            st.success(f"✅ Database exists")
            st.metric("Total Records", stats['row_count'])
        else:
            st.info("📭 Database empty - upload file to create")
        
        st.markdown("---")
        st.header("📋 Required Columns")
        for col in REQUIRED_COLUMNS:
            st.write(f"• {col}")
        
        st.markdown("---")
        st.header("⚠️ Database Actions")
        
        # Delete entire database option
        if stats['exists'] and stats['row_count'] > 0:
            st.warning("⚠️ **Danger Zone**")
            st.caption(f"This will permanently delete all {stats['row_count']} records from the database.")
            
            # Use session state for confirmation
            if 'confirm_delete_db' not in st.session_state:
                st.session_state.confirm_delete_db = False
            
            if not st.session_state.confirm_delete_db:
                if st.button("🗑️ Delete Entire Database", type="secondary", key="delete_db_btn"):
                    st.session_state.confirm_delete_db = True
                    st.rerun()
            else:
                st.error("⚠️ **Are you sure?** This action cannot be undone!")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirm Delete", type="primary", key="confirm_delete_btn"):
                        with st.spinner("Deleting database..."):
                            success, message = delete_entire_database(engine)
                        if success:
                            st.success(message)
                            st.session_state.confirm_delete_db = False
                            st.rerun()
                        else:
                            st.error(message)
                            st.session_state.confirm_delete_db = False
                with col2:
                    if st.button("❌ Cancel", key="cancel_delete_btn"):
                        st.session_state.confirm_delete_db = False
                        st.rerun()
        else:
            st.info("📭 No data to delete")
    
    # Main content area
    tab1, tab2 = st.tabs(["📤 Upload & Auto Update", "📋 View Database"])
    
    with tab1:
        st.header("Drag & Drop Excel File")
        st.info("📋 **Required columns:** " + ", ".join(REQUIRED_COLUMNS))
        
        # Update Mode selection on upload page
        st.markdown("---")
        st.subheader("⚙️ Update Mode")
        update_mode = st.radio(
            "Choose update method:",
            options=['Replace', 'Append'],
            help="Replace: Overwrite all data. Append: Add new records.",
            horizontal=True,
            key="update_mode_radio"
        )
        update_mode_lower = update_mode.lower()
        
        # Show explanation based on selected mode
        if update_mode == 'Replace':
            st.info("💡 **Replace Mode (Smart Update):** This will **update existing records** that match by Email address and **add new records** from the file. Existing records not in the file will **be kept**. No data will be deleted.")
        else:  # Append
            st.info("💡 **Append Mode (No Duplicates):** This will **add only NEW records** to the existing database. Records with duplicate Email addresses will be **skipped automatically**. Existing records will be kept unchanged, and only new emails will be added.")
        
        # File uploader with auto-update
        uploaded_file = st.file_uploader(
            "Drop your Excel file here (supports .xlsx, .xls)",
            type=['xlsx', 'xls'],
            help="The file will be automatically processed and updated to database"
        )
        
        # Auto-process when file is uploaded
        if uploaded_file is not None:
            # Check if this is a new file
            file_id = f"{uploaded_file.name}_{uploaded_file.size}"
            is_new_file = st.session_state.last_file != file_id
            
            if is_new_file:
                st.session_state.last_file = file_id
                
                try:
                    with st.spinner("🔄 Processing file..."):
                        # Validate file format
                        is_valid_file, file_extension, file_result = validate_file_format(uploaded_file)
                        
                        if not is_valid_file:
                            st.error(f"❌ **Error:** {file_result}")
                            st.stop()
                        
                        engine_name = file_result
                        
                        # Save file to temp for processing
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
                            uploaded_file.seek(0)
                            tmp_file.write(uploaded_file.read())
                            tmp_file_path = tmp_file.name
                        
                        try:
                            # Read Excel file - get sheet names
                            success, sheet_names, engine_name, error_msg, error_details = read_excel_file(
                                tmp_file_path, file_extension, engine_name
                            )
                            
                            if not success:
                                st.error(error_msg)
                                if error_details:
                                    st.warning(error_details)
                                    if "Encrypted" in error_msg or "Password-Protected" in error_msg:
                                        st.markdown("**📋 What this means:**")
                                        st.info("• The file might be password-protected")
                                        st.info("• The file might be saved as an 'Internal' Excel format")
                                        st.info("• The file might have security/permission restrictions")
                                    else:
                                        st.markdown("**🔧 Solution:** The file needs to be properly saved in Excel.")
                                        st.info("**Please follow these steps:**")
                                        st.info("1. ✅ Open the file in Excel")
                                        st.info("2. ✅ Click **File** → **Save As**")
                                        st.info("3. ✅ In the dropdown, select **'Excel Workbook (*.xlsx)'**")
                                        st.info("4. ✅ Click **Save** (you can overwrite the file or use a new name)")
                                        st.info("5. ✅ Upload the newly saved file here")
                                st.stop()
                            
                            # If multiple sheets, let user choose
                            if len(sheet_names) > 1:
                                selected_sheets = st.multiselect(
                                    "📋 Select sheet(s) to process (can select multiple for bulk upload):",
                                    options=sheet_names,
                                    default=[sheet_names[0]],
                                    key="sheet_selector"
                                )
                                
                                if not selected_sheets:
                                    st.warning("⚠️ Please select at least one sheet to process.")
                                    st.stop()
                            else:
                                selected_sheets = [sheet_names[0]]
                                st.info(f"📋 Using sheet: **{sheet_names[0]}**")
                            
                            # Process selected sheets
                            all_processed_data = []
                            processed_sheets = []
                            failed_sheets = []
                            
                            for sheet_name in selected_sheets:
                                # Process each sheet
                                success, df_processed, error_msg, missing_cols, column_mapping = process_sheet(
                                    tmp_file_path, sheet_name, engine_name
                                )
                                
                                if success:
                                    all_processed_data.append(df_processed)
                                    processed_sheets.append({
                                        'name': sheet_name,
                                        'rows': len(df_processed),
                                        'mapping': column_mapping
                                    })
                                else:
                                    failed_sheets.append({
                                        'name': sheet_name,
                                        'error': error_msg,
                                        'missing_cols': missing_cols
                                    })
                            
                            # Show validation results
                            if failed_sheets:
                                st.error(f"❌ **Validation failed for {len(failed_sheets)} sheet(s):**")
                                for failed in failed_sheets:
                                    with st.expander(f"❌ Sheet: {failed['name']}"):
                                        st.error(f"**Error:** {failed['error']}")
                                        if failed['missing_cols']:
                                            st.warning(f"⚠️ Missing columns: {', '.join(failed['missing_cols'])}")
                                            st.info(f"**Required columns:** {', '.join(REQUIRED_COLUMNS)}")
                                
                                # Only stop if all sheets failed
                                if len(failed_sheets) == len(selected_sheets):
                                    st.stop()
                            
                            # Show successful sheets
                            if processed_sheets:
                                st.success(f"✅ **Successfully processed {len(processed_sheets)} sheet(s)!**")
                                
                                # Show column mapping only if there are differences
                                for sheet_info in processed_sheets:
                                    mapping_changes = {k: v for k, v in sheet_info['mapping'].items() if k != v}
                                    if mapping_changes:
                                        st.write(f"**Sheet '{sheet_info['name']}' column mapping:**")
                                        for req_col, found_col in mapping_changes.items():
                                            st.write(f"  • '{req_col}' → '{found_col}'")
                            
                            # Combine all processed data from all sheets
                            if all_processed_data:
                                df_processed = pd.concat(all_processed_data, ignore_index=True)
                                
                                # Remove duplicates based on Email (if any sheet had duplicate emails)
                                df_processed = df_processed.drop_duplicates(subset=['Email'], keep='last')
                                
                                st.info(f"📋 **Found columns in Excel:** {', '.join(REQUIRED_COLUMNS)}")
                                st.info(f"📊 **Total rows from {len(processed_sheets)} sheet(s):** {len(df_processed)}")
                                
                                # Display preview
                                st.success(f"✅ File loaded successfully! Found {len(df_processed)} total rows")
                                st.subheader("📊 Data Preview")
                                st.dataframe(df_processed.head(10), use_container_width=True)
                                
                                # Show summary of processed sheets
                                if len(processed_sheets) > 1:
                                    st.markdown("---")
                                    st.subheader("📋 Processed Sheets Summary")
                                    summary_data = {
                                        'Sheet Name': [s['name'] for s in processed_sheets],
                                        'Rows': [s['rows'] for s in processed_sheets]
                                    }
                                    summary_df = pd.DataFrame(summary_data)
                                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                                
                                # Auto-update database
                                st.markdown("---")
                                with st.spinner(f"🔄 Updating database ({update_mode_lower} mode)..."):
                                    result = update_database(engine, df_processed, update_mode_lower)
                                
                                if isinstance(result, tuple):
                                    success, message = result
                                    result_dict = None
                                else:
                                    success, result_dict = result
                                    # Extract message string from result_dict
                                    if isinstance(result_dict, dict):
                                        message = result_dict.get('message', 'Update completed successfully')
                                    elif isinstance(result_dict, str):
                                        message = result_dict
                                    else:
                                        message = 'Update completed successfully'
                                
                                if success:
                                    st.success(message)
                                    st.balloons()
                                    st.session_state.db_updated = True
                                    
                                    # Show summary metrics
                                    st.markdown("---")
                                    st.subheader("📊 Summary")
                                    
                                    if update_mode_lower == 'append' and isinstance(result_dict, dict):
                                        # Append mode summary
                                        if result_dict.get('duplicates_count', 0) > 0:
                                            col1, col2, col3, col4 = st.columns(4)
                                            with col1:
                                                st.metric("Rows Processed", len(df_processed))
                                            with col2:
                                                st.metric("New Rows Added", result_dict.get('new_count', 0))
                                            with col3:
                                                st.metric("Duplicates Skipped", result_dict.get('duplicates_count', 0))
                                            with col4:
                                                new_stats = get_db_stats(engine)
                                                st.metric("Total in DB", new_stats['row_count'])
                                        else:
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.metric("Rows Processed", len(df_processed))
                                            with col2:
                                                st.metric("New Rows Added", result_dict.get('new_count', 0))
                                            with col3:
                                                new_stats = get_db_stats(engine)
                                                st.metric("Total in DB", new_stats['row_count'])
                                    elif update_mode_lower == 'replace' and isinstance(result_dict, dict):
                                        # Replace mode summary
                                        col1, col2, col3, col4 = st.columns(4)
                                        with col1:
                                            st.metric("Rows Processed", len(df_processed))
                                        with col2:
                                            st.metric("Updated", result_dict.get('updated_count', 0))
                                        with col3:
                                            st.metric("Added", result_dict.get('new_count', 0))
                                        with col4:
                                            st.metric("Kept", result_dict.get('kept_count', 0))
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.metric("Columns", len(df_processed.columns))
                                        with col2:
                                            new_stats = get_db_stats(engine)
                                            st.metric("Total in DB", new_stats['row_count'])
                                    else:
                                        # Generic summary
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("Rows Processed", len(df_processed))
                                        with col2:
                                            st.metric("Columns", len(df_processed.columns))
                                        with col3:
                                            new_stats = get_db_stats(engine)
                                            st.metric("Total in DB", new_stats['row_count'])
                                    
                                    # Show detailed changes if Replace mode was used and there are changes
                                    if update_mode_lower == 'replace' and isinstance(result_dict, dict) and result_dict.get('changes'):
                                        changes = result_dict['changes']
                                        if len(changes) > 0:
                                            st.markdown("---")
                                            st.subheader("📝 Change Details")
                                            st.info(f"**{len(changes)} record(s) were updated.**")
                                            
                                            # Create a comprehensive table showing all changes
                                            all_changes_data = []
                                            
                                            for change in changes:
                                                # Clean email from HTML tags if any
                                                email = change.get('email', '')
                                                if isinstance(email, str) and '<a href' in email:
                                                    import re
                                                    # Extract email from HTML anchor tag
                                                    email_match = re.search(r'>(.*?)</a>', email)
                                                    if email_match:
                                                        email = email_match.group(1)
                                                    else:
                                                        # Try to extract from href
                                                        email_match = re.search(r'mailto:(.*?)[">]', email)
                                                        if email_match:
                                                            email = email_match.group(1)
                                                
                                                # Create one row for each changed column in this record
                                                changed_cols = change.get('changed_columns', {})
                                                for col_name, col_change in changed_cols.items():
                                                    all_changes_data.append({
                                                        'Email': email,
                                                        'Name': change.get('name', ''),
                                                        'Surname': change.get('surname', ''),
                                                        'Column': col_name,
                                                        'Old Value': col_change.get('old', ''),
                                                        'New Value': col_change.get('new', '')
                                                    })
                                            
                                            # Display as table
                                            if all_changes_data:
                                                changes_table_df = pd.DataFrame(all_changes_data)
                                                
                                                # Sort by Email and Column for better readability
                                                changes_table_df = changes_table_df.sort_values(['Email', 'Column'])
                                                
                                                # Display the changes table
                                                st.dataframe(
                                                    changes_table_df[['Email', 'Name', 'Surname', 'Column', 'Old Value', 'New Value']],
                                                    use_container_width=True,
                                                    height=400,
                                                    hide_index=True
                                                )
                                                
                                                # Download option
                                                csv_changes = changes_table_df.to_csv(index=False).encode('utf-8')
                                                st.download_button(
                                                    label="📥 Download Changes as CSV",
                                                    data=csv_changes,
                                                    file_name=f"changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                                    mime="text/csv",
                                                    key="download_changes"
                                                )
                                else:
                                    st.error(message)
                                    
                        finally:
                            # Clean up temp file
                            if tmp_file_path and os.path.exists(tmp_file_path):
                                try:
                                    time.sleep(0.1)
                                    os.unlink(tmp_file_path)
                                except PermissionError:
                                    try:
                                        import ctypes
                                        ctypes.windll.kernel32.SetFileAttributesW(tmp_file_path, 128)
                                        os.unlink(tmp_file_path)
                                    except:
                                        pass
                                except Exception:
                                    pass
                        
                except Exception as e:
                    st.error(f"❌ Error processing file: {str(e)}")
                    import traceback
                    with st.expander("🔍 Error Details"):
                        st.code(traceback.format_exc())
        
        else:
            st.info("👆 **Drag and drop an Excel file above to get started**")
    
    with tab2:
        st.header("📋 Database Records")
        
        # Load and display data from database
        df_db = load_data_from_db(engine)
            
        if len(df_db) > 0:
            # Display summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(df_db))
            with col2:
                st.metric("Columns", len(df_db.columns))
            with col3:
                non_empty = df_db.replace('', pd.NA).notna().sum().sum()
                st.metric("Filled Cells", non_empty)
            
            st.markdown("---")
            
            # Search and filter
            st.subheader("🔍 Search & Filter")
            search_col1, search_col2 = st.columns([3, 1])
            with search_col1:
                search_term = st.text_input("Search in all columns:", key="search_input")
            with search_col2:
                st.write("")
                st.write("")
                if st.button("🔄 Refresh", key="refresh_btn"):
                    st.rerun()
            
            # Filter data if search term provided
            if search_term:
                mask = df_db.astype(str).apply(
                    lambda x: x.str.contains(search_term, case=False, na=False)
                ).any(axis=1)
                df_display = df_db[mask]
                st.info(f"📊 Found {len(df_display)} records matching '{search_term}'")
            else:
                df_display = df_db
            
            # Display data with edit/delete options
            st.subheader("📊 Data Table")
            st.dataframe(df_display, use_container_width=True, height=500)
            
            st.markdown("---")
            st.subheader("✏️ Edit or Delete Records")
            
            # Select row to edit/delete
            row_indices = list(range(len(df_display)))
            
            def format_row_label(idx):
                row = df_display.iloc[idx]
                name = str(row.get('Name', 'N/A'))
                surname = str(row.get('Surname', 'N/A'))
                company = str(row.get('Company', 'N/A'))
                return f"Row {idx+1} - {name} {surname} ({company})"
            
            selected_row_idx = st.selectbox(
                "Select row to edit or delete:",
                options=row_indices,
                format_func=format_row_label,
                key="row_selector"
            )
            
            if selected_row_idx is not None:
                selected_row = df_display.iloc[selected_row_idx]
                
                # Create two columns for edit and delete
                edit_col, delete_col = st.columns(2)
                
                with edit_col:
                    st.markdown("#### ✏️ Edit Row")
                    # Create editable form
                    edited_data = {}
                    for col in REQUIRED_COLUMNS:
                        edited_data[col] = st.text_input(
                            col,
                            value=str(selected_row[col]) if col in selected_row else "",
                            key=f"edit_{col}_{selected_row_idx}"
                        )
                    
                    if st.button("💾 Save Changes", key=f"save_{selected_row_idx}", type="primary"):
                        # Convert row to dict for comparison
                        old_row_dict = selected_row.to_dict()
                        # Check if anything changed
                        has_changes = any(str(old_row_dict.get(col, '')) != edited_data[col] for col in REQUIRED_COLUMNS)
                        
                        if has_changes:
                            with st.spinner("Updating row..."):
                                success, message = update_row_in_db(engine, old_row_dict, edited_data)
                            if success:
                                st.success(message)
                                st.rerun()
                        else:
                                st.error(message)
                    else:
                            st.info("No changes detected.")
                
                with delete_col:
                    st.markdown("#### 🗑️ Delete Row")
                    st.write("**Current row data:**")
                    for col in REQUIRED_COLUMNS:
                        if col in selected_row:
                            st.write(f"**{col}:** {selected_row[col]}")
                    
                    st.warning("⚠️ This action cannot be undone!")
                    if st.button("🗑️ Delete Row", key=f"delete_{selected_row_idx}", type="secondary"):
                        # Convert row to dict
                        row_dict = selected_row.to_dict()
                        with st.spinner("Deleting row..."):
                            success, message = delete_row_from_db(engine, row_dict)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
            
            # Download option
            st.markdown("---")
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("📭 **Database is empty. Upload an Excel file to add data.**")

if __name__ == "__main__":
    main()
