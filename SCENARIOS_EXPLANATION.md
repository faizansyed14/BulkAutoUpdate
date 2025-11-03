# 📚 App Scenarios Explained Simply

## 🎯 **How the App Works - All Scenarios**

---

## 📤 **Scenario 1: Upload & Update Modes**

### **Mode A: Replace Mode (Smart Update)** 🔄

**What it does:**
- Updates existing records (matched by Email)
- Adds new records from the file
- Keeps existing records NOT in the file
- **NEVER deletes data** unless you manually delete

**How it works:**
1. Upload your Excel file
2. App looks at the **Email** column in each row
3. For each row in your Excel:
   - **If Email exists in database:** Updates that record with new data
   - **If Email is NEW:** Adds it as a new record
   - **If Email is NOT in file:** Keeps the existing record unchanged

**Example:**
```
Database BEFORE:
- Email: john@example.com, Name: John, Company: ABC
- Email: jane@example.com, Name: Jane, Company: XYZ
- Email: bob@example.com, Name: Bob, Company: DEF

Excel file uploaded:
- Email: john@example.com, Name: John Smith, Company: ABC Corp  ← UPDATES
- Email: jane@example.com, Name: Jane Doe, Company: XYZ      ← UPDATES (no change)
- Email: alice@example.com, Name: Alice, Company: GHI         ← ADDS NEW

Database AFTER:
- Email: john@example.com, Name: John Smith, Company: ABC Corp  ✅ UPDATED
- Email: jane@example.com, Name: Jane Doe, Company: XYZ        ✅ KEPT
- Email: bob@example.com, Name: Bob, Company: DEF             ✅ KEPT (not in file)
- Email: alice@example.com, Name: Alice, Company: GHI        ✅ ADDED
```

**Result:** 
- ✅ 2 records updated (john changed, jane stayed same)
- ✅ 1 new record added (alice)
- ✅ 1 existing record kept (bob - not in file)

---

### **Mode B: Append Mode** ➕

**What it does:**
- Adds ALL rows from Excel file as NEW records
- Does NOT update existing records
- Does NOT check for duplicates
- Simply adds everything at the end

**How it works:**
1. Upload your Excel file
2. App takes ALL rows from Excel
3. Adds them ALL to the database (even if Email already exists)

**Example:**
```
Database BEFORE:
- Email: john@example.com, Name: John, Company: ABC

Excel file uploaded:
- Email: john@example.com, Name: John Smith, Company: ABC Corp
- Email: jane@example.com, Name: Jane, Company: XYZ

Database AFTER:
- Email: john@example.com, Name: John, Company: ABC          ← OLD (unchanged)
- Email: john@example.com, Name: John Smith, Company: ABC Corp ← DUPLICATE ADDED
- Email: jane@example.com, Name: Jane, Company: XYZ          ← NEW ADDED
```

**Result:** 
- ⚠️ You get duplicate records (john appears twice)
- ✅ All Excel rows are added to database

**Use this when:** You want to add new records without touching existing ones

---

## 📋 **Scenario 2: View Database Tab**

### **A. Search & Filter** 🔍

**What it does:**
- Search across ALL columns
- Shows only matching records

**How it works:**
1. Type in search box (e.g., "John")
2. App searches Name, Surname, Email, Company, Position, Phone
3. Shows only rows containing "John"

**Example:**
```
Search: "john"
Results: All records where ANY column contains "john"
- john@example.com
- Johnson (in name)
- John's Company (in company)
```

---

### **B. Edit Single Row** ✏️

**What it does:**
- Updates ONE specific row in the database
- Changes only the fields you edit

**How it works:**
1. Select a row from dropdown
2. Edit the text fields you want to change
3. Click "Save Changes"
4. Only that specific row is updated

**Example:**
```
Before:
- Email: john@example.com, Name: John, Company: ABC

You edit:
- Name: John → John Smith
- Company: ABC → ABC Corp

After:
- Email: john@example.com, Name: John Smith, Company: ABC Corp
- Other rows unchanged
```

---

### **C. Delete Single Row** 🗑️

**What it does:**
- Deletes ONE specific row from database
- Cannot be undone

**How it works:**
1. Select a row from dropdown
2. Click "Delete Row"
3. That specific row is permanently removed

**Example:**
```
Before: 3 records
- john@example.com
- jane@example.com
- bob@example.com

You delete: jane@example.com

After: 2 records
- john@example.com
- bob@example.com
```

---

### **D. Delete Entire Database** ⚠️

**What it does:**
- Deletes ALL records from database
- Removes the entire table
- Cannot be undone

**How it works:**
1. Go to sidebar → "Database Actions"
2. Click "🗑️ Delete Entire Database" (first click)
3. Click "✅ Confirm Delete" (second click - confirmation)
4. All data is permanently deleted

**Safety:**
- ⚠️ Two-step confirmation required
- ⚠️ Shows warning with record count
- ⚠️ Must confirm to proceed

**Example:**
```
Before: 100 records in database

After: 0 records
Database is empty (but ready for new uploads)
```

---

## 🔄 **Scenario 3: Bulk Sheet Upload**

**What it does:**
- Process multiple Excel sheets from one file
- Combines data from all selected sheets
- Removes duplicate Emails (keeps last one)

**How it works:**
1. Upload Excel file with multiple sheets
2. Select which sheets to process (can select multiple)
3. App processes each sheet separately
4. Combines all results into one dataset
5. Removes duplicates based on Email

**Example:**
```
Excel file has 3 sheets:
- Sheet1: 10 records
- Sheet2: 15 records  
- Sheet3: 5 records

You select: Sheet1 and Sheet2

Result: 25 records combined (duplicates removed)
- If same email in both sheets, keeps the one from Sheet2
```

---

## 📊 **How Email Matching Works**

### **Key Point: Email is the Unique Identifier** 🔑

The app uses **Email** to identify records:
- ✅ Same Email = Same Person = Update existing record
- ✅ New Email = New Person = Add new record
- ✅ Email not in file = Keep existing record

**Email Matching Rules:**
1. **Case-insensitive:** john@example.com = JOHN@EXAMPLE.COM
2. **Whitespace ignored:** " john@example.com " = "john@example.com"
3. **Exact match required** (after normalization)

**Example:**
```
Database has:
- Email: "  John@Example.com  " (with spaces and mixed case)

Excel file has:
- Email: "john@example.com" (lowercase, no spaces)

Result: ✅ MATCHES - Updates the existing record
```

---

## ✅ **Summary: What Gets Updated/Deleted**

### **During Upload (Replace Mode):**
- ✅ **Updated:** Records with matching Email
- ✅ **Added:** Records with new Email
- ✅ **Kept:** Existing records NOT in file
- ❌ **Never Deleted:** Data is never automatically deleted

### **Manual Operations:**
- ✏️ **Edit Row:** Updates one specific record
- 🗑️ **Delete Row:** Removes one specific record
- ⚠️ **Delete Database:** Removes ALL records

---

## 🎯 **Quick Reference**

| Action | What Happens | Can Undo? |
|--------|-------------|------------|
| **Upload (Replace)** | Smart update: updates existing, adds new, keeps old | No |
| **Upload (Append)** | Adds all rows as new records (may create duplicates) | No |
| **Edit Row** | Updates one specific record | No |
| **Delete Row** | Removes one specific record | No |
| **Delete Database** | Removes ALL records | No |

---

## 💡 **Tips:**

1. **Use Replace Mode** for most uploads (smart, no duplicates)
2. **Use Append Mode** only when you want duplicates
3. **Email must be unique** - same email = same person
4. **Download CSV** before major operations (backup)
5. **Two-step delete** prevents accidents

---

**Questions?** All operations are logged and shown in the UI with clear messages!

