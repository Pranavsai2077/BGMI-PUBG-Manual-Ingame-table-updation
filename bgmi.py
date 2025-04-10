import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from bs4 import BeautifulSoup
import os
import shutil

HTML_FILE = "BGMI.html"
BACKUP_FILE = "BGMI.html.bak"
NUM_STATUS_INDICATORS = 4
AUTO_SAVE_DELAY_MS = 2000 # Delay in milliseconds (e.g., 2000 = 2 seconds)

data = []
soup = None
auto_save_job = None # Variable to store the pending .after job ID
sort_column_cache = {"column": "#", "reverse": False} # Default sort column is now '#'

# --- Utility Functions (handle_load_error, load_data, update_table) ---
# (Keep handle_load_error as before)
def handle_load_error(message):
    """Handles errors during data loading."""
    messagebox.showerror("Load Error", message)
    # Return default empty data and basic HTML structure
    return [], BeautifulSoup("<html><head><title>Standings</title></head><body><table><thead><tr><th>#</th><th>Team</th><th>Points</th><th>Status</th></tr></thead><tbody></tbody></table></body></html>", "html.parser")

def load_data():
    """Loads data from the HTML file with error handling."""
    global soup, status_label
    try:
        if not os.path.exists(HTML_FILE):
            default_data, default_soup = handle_load_error(f"Error: {HTML_FILE} not found. Created default empty structure.")
            soup = default_soup
            status_label.config(text=f"Error: {HTML_FILE} not found. Using empty table.", fg="orange")
            return default_data, soup

        with open(HTML_FILE, "r", encoding="utf-8") as file:
            soup = BeautifulSoup(file, "html.parser")

        table = soup.find("table")
        if not table:
             default_data, default_soup = handle_load_error(f"Error: No <table> tag found in {HTML_FILE}.")
             soup = default_soup
             status_label.config(text=f"Error: No <table> tag found in {HTML_FILE}. Using empty table.", fg="red")
             return default_data, soup

        header = table.find('thead') or table
        header_cols = header.find_all("th") if header else []
        # Check if first header is '#' or 'Rank' for backward compatibility maybe? For now, expect '#'
        if len(header_cols) < 4 or header_cols[0].text.strip() not in ("#", "Rank"):
             default_data, default_soup = handle_load_error(f"Error: Expected table headers '#', 'Team', 'Points', 'Status'. Found incomplete/wrong headers.")
             soup = default_soup
             status_label.config(text=f"Error: Table header columns incorrect in {HTML_FILE}. Using empty table.", fg="red")
             return default_data, soup

        loaded_data = []
        data_rows = table.find('tbody') or table
        tbody_rows = data_rows.find_all("tr")
        # Adjust loop if header row is inside tbody without thead
        start_index = 1 if table.find('thead') else (1 if tbody_rows and tbody_rows[0].find('th') else 0)

        for i, row in enumerate(tbody_rows[start_index:], start=1):
            if not row.find("td"): continue

            cols = row.find_all("td")
            if len(cols) < 4:
                messagebox.showwarning("Load Warning", f"Row {i} in {HTML_FILE} has less than 4 columns (<td>). Skipping.")
                continue

            try:
                rank_num = int(cols[0].text.strip()) # Internally still rank number
                team = cols[1].text.strip()
                points = int(cols[2].text.strip())
                status = cols[3].text.strip().replace("🟩", "✅").replace("🟥", "❌")
                if len(status) != NUM_STATUS_INDICATORS:
                     messagebox.showwarning("Load Warning", f"Row {i} (# {rank_num}) has status length {len(status)}, expected {NUM_STATUS_INDICATORS}. Adjusting.")
                     status = (status + "❌" * NUM_STATUS_INDICATORS)[:NUM_STATUS_INDICATORS]

                loaded_data.append([rank_num, team, points, status]) # Data structure: [rank_num, team, points, status]
            except ValueError:
                 messagebox.showwarning("Load Warning", f"Row {i} in {HTML_FILE} has non-numeric # or Points. Skipping.")
                 continue
            except IndexError:
                 messagebox.showwarning("Load Warning", f"Row {i} in {HTML_FILE} structure issue (IndexError). Skipping.")
                 continue

        status_label.config(text="Data loaded successfully.", fg="blue")
        return loaded_data, soup

    except FileNotFoundError:
        default_data, default_soup = handle_load_error(f"Error: {HTML_FILE} not found.")
        soup = default_soup
        status_label.config(text=f"Error: {HTML_FILE} not found. Using empty table.", fg="red")
        return default_data, soup
    except Exception as e:
        default_data, default_soup = handle_load_error(f"An unexpected error occurred during loading: {e}")
        soup = default_soup
        status_label.config(text=f"Unexpected load error: {e}. Using empty table.", fg="red")
        return default_data, soup

def update_table():
    """Clears and repopulates the Treeview."""
    for row in tree.get_children():
        tree.delete(row)
    for row_data in data:
        tree.insert("", "end", values=row_data)

# --- Auto Save Logic ---
def perform_save():
    """The actual save function, separated for clarity."""
    global data, soup, status_label
    if not soup:
        status_label.config(text="HTML structure missing, cannot save.", fg="red")
        return

    status_label.config(text="Auto-saving...", fg="orange") # Indicate saving started
    root.update_idletasks() # Ensure message updates

    # Backup
    try:
        if os.path.exists(HTML_FILE):
            shutil.copy2(HTML_FILE, BACKUP_FILE)
    except Exception as e:
        # Log backup error but proceed with save attempt
        print(f"Warning: Could not create backup file: {e}")
        status_label.config(text="Backup failed, attempting save...", fg="orange")
        root.update_idletasks()

    # Sort data by Rank (# column, index 0) before saving
    current_data = sorted(data, key=lambda x: int(x[0]))

    table = soup.find("table")
    if not table:
        status_label.config(text="HTML <table> tag missing, cannot save.", fg="red")
        return

    # Ensure thead exists
    thead = table.find('thead')
    if not thead:
         thead = soup.new_tag('thead')
         header_row = soup.new_tag('tr')
         # Use '#' for header now
         for col_name in ("#", "Team", "Points", "Status"):
             th = soup.new_tag('th')
             th.string = col_name
             header_row.append(th)
         thead.append(header_row)
         table.insert(0, thead)

    # Ensure tbody exists and clear it
    tbody = table.find('tbody')
    if not tbody:
        tbody = soup.new_tag('tbody')
        existing_rows = [row for row in table.find_all('tr') if not row.find('th')]
        for row in existing_rows:
            tbody.append(row.extract())
        table.append(tbody)
    else:
        tbody.clear()

    # Add new rows from sorted data into tbody
    for row_values in current_data:
        new_row = soup.new_tag("tr")
        for i, cell_value in enumerate(row_values):
            new_td = soup.new_tag("td")
            if i == 3: # Status column index
                cell_value = str(cell_value).replace("✅", "🟩").replace("❌", "🟥")
            new_td.string = str(cell_value)
            new_row.append(new_td)
        tbody.append(new_row)

    # Save the modified HTML
    try:
        with open(HTML_FILE, "w", encoding="utf-8") as file:
            # Remove the <h1> title if it exists before writing
            h1_title = soup.find("h1")
            if h1_title:
                h1_title.decompose() # Remove the h1 tag
            # Also remove the <title> tag content in <head> if needed? No, keep window title.

            file.write(soup.prettify())
        status_label.config(text="Data auto-saved successfully!", fg="green")
        data = current_data # Ensure internal data matches saved sorted data
    except Exception as e:
        status_label.config(text=f"Error auto-saving data: {e}", fg="red")
        # If save fails, maybe trigger manual save option? For now, just report error.

def schedule_save():
    """Schedules the perform_save function after a delay, cancelling previous jobs."""
    global auto_save_job, root, status_label
    # Cancel any existing scheduled save
    if auto_save_job:
        root.after_cancel(auto_save_job)

    # Schedule the save
    status_label.config(text="Changes detected, scheduling auto-save...", fg="blue")
    auto_save_job = root.after(AUTO_SAVE_DELAY_MS, perform_save)


# --- GUI Action Functions (select_entry, add_entry, update_entry, delete_entry, clear_all_data, toggle_status, clear_entry_fields) ---

def select_entry(event):
    """Populates entry fields when a row is selected."""
    selected_item = tree.selection()
    if selected_item:
        values = tree.item(selected_item[0], "values")
        # Use column indices now which are stable: 0=#, 1=Team, 2=Points, 3=Status
        rank_var.set(values[0])
        team_var.set(values[1])
        points_var.set(values[2])
        status_string = values[3]
        for i, btn in enumerate(status_buttons):
            if i < len(status_string):
                is_alive = (status_string[i] == "✅")
                btn.config(text="✅" if is_alive else "❌", relief=tk.SUNKEN if is_alive else tk.RAISED)
            else:
                 btn.config(text="❌", relief=tk.RAISED)
        status_label.config(text="Entry selected.", fg="blue")
    else:
         clear_entry_fields()

def add_entry():
    """Adds a new entry and schedules an auto-save."""
    global data
    # Use column indices for data structure: 0=#, 1=Team, 2=Points, 3=Status
    new_rank_str = rank_var.get().strip()
    new_team = team_var.get().strip()
    new_points_str = points_var.get().strip()
    new_status = ''.join(["✅" if btn["relief"] == tk.SUNKEN else "❌" for btn in status_buttons])

    # Validation...
    if not new_team:
        status_label.config(text="Team name cannot be empty!", fg="red"); return
    try:
        new_rank = int(new_rank_str)
    except ValueError:
        status_label.config(text="# must be a number!", fg="red"); return
    try:
        new_points = int(new_points_str)
    except ValueError:
        status_label.config(text="Points must be a number!", fg="red"); return

    for entry in data:
        if entry[0] == new_rank:
            status_label.config(text=f"# {new_rank} already exists!", fg="red"); return

    new_entry_data = [new_rank, new_team, new_points, new_status]
    data.append(new_entry_data)
    tree.insert("", "end", values=new_entry_data)
    status_label.config(text="Entry added.", fg="green")
    clear_entry_fields()
    new_item_id = tree.get_children()[-1]
    if new_item_id:
        tree.selection_set(new_item_id); tree.focus(new_item_id); tree.see(new_item_id)
    schedule_save() # Schedule save after adding

def update_entry():
    """Updates the status of the selected entry and schedules an auto-save."""
    global data
    selected_item = tree.selection()
    if selected_item:
        selected_item_id = selected_item[0]
        current_values = tree.item(selected_item_id, "values")
        # Use indices: 0=#, 1=Team, 2=Points, 3=Status
        current_rank = int(current_values[0])
        current_team = current_values[1]
        current_points = int(current_values[2])
        new_status = ''.join(["✅" if btn["relief"] == tk.SUNKEN else "❌" for btn in status_buttons])

        tree.item(selected_item_id, values=(current_rank, current_team, current_points, new_status))

        updated = False
        for i, entry in enumerate(data):
             if entry[0] == current_rank:
                 data[i] = [current_rank, current_team, current_points, new_status]
                 updated = True
                 break
        if updated:
             status_label.config(text="Entry status updated.", fg="green")
             schedule_save() # Schedule save after updating
        else:
             status_label.config(text="Error updating data list.", fg="red")
    else:
        status_label.config(text="Please select a row to update!", fg="red")

def delete_entry():
    """Deletes the selected entry and schedules an auto-save."""
    global data
    selected_item = tree.selection()
    if selected_item:
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected entry?"):
            selected_item_id = selected_item[0]
            values = tree.item(selected_item_id, "values")
            try:
                 rank_to_delete = int(values[0]) # Index 0 is '#'
                 tree.delete(selected_item_id)
                 data_len_before = len(data)
                 data = [entry for entry in data if entry[0] != rank_to_delete]
                 if len(data) < data_len_before:
                      status_label.config(text="Entry deleted.", fg="orange")
                      clear_entry_fields()
                      schedule_save() # Schedule save after deleting
                 else:
                      status_label.config(text="Error deleting from data list.", fg="red")
            except (ValueError, IndexError):
                 status_label.config(text="Error reading # from selected item.", fg="red")
    else:
        status_label.config(text="Please select a row to delete!", fg="red")


def clear_all_data():
    """Clears all data and schedules an auto-save."""
    global data, soup
    if messagebox.askyesno("Confirm Clear All", "Are you sure you want to clear ALL data?"):
        data.clear()
        for row in tree.get_children():
            tree.delete(row)
        status_label.config(text="All data cleared.", fg="red")
        clear_entry_fields()
        schedule_save() # Schedule save after clearing


def toggle_status(index):
    """Toggles a status button. Does NOT auto-save immediately, relies on Update Status click."""
    # Note: We don't schedule save here, only when "Update Status" is clicked.
    if status_buttons[index]["relief"] == tk.SUNKEN:
        status_buttons[index].config(text="❌", relief=tk.RAISED)
    else:
        status_buttons[index].config(text="✅", relief=tk.SUNKEN)


def clear_entry_fields():
    """Clears the input fields and resets status buttons."""
    rank_var.set("")
    team_var.set("")
    points_var.set("")
    for btn in status_buttons:
        btn.config(text="❌", relief=tk.RAISED)
    tree.selection_set(())


# --- Sorting Logic ---
def sort_column(tv, col, reverse):
    """Sorts the Treeview and data list by the clicked column."""
    global data, sort_column_cache
    try:
        # Map display column name to internal data index
        col_map = {"#": 0, "Team": 1, "Points": 2, "Status": 3}
        if col not in col_map:
            raise ValueError(f"Unknown column: {col}")
        col_index = col_map[col]

        if col in ("#", "Points"):
             key_func = lambda x: int(x[col_index])
        else: # Team, Status (string sort)
             key_func = lambda x: str(x[col_index]).lower()

        data.sort(key=key_func, reverse=reverse)

    except ValueError as e:
        messagebox.showerror("Sort Error", f"Cannot sort column '{col}'. Check data type. Error: {e}")
        return
    except IndexError:
         messagebox.showerror("Sort Error", f"Invalid column index for '{col}'.")
         return

    update_table() # Refresh treeview based on sorted 'data'

    # Update header arrows
    display_cols = ("#", "Team", "Points", "Status") # Use display names for headers
    for c in display_cols:
         tv.heading(c, text=c)
    tv.heading(col, text=col + (' ▼' if reverse else ' ▲'), command=lambda _col=col: sort_column(tv, _col, not reverse))
    sort_column_cache = {"column": col, "reverse": reverse}


# --- Window Closing Logic ---
def on_closing():
    """Handles the window close event cleanly."""
    global auto_save_job
    # Cancel any pending auto-save before closing
    if auto_save_job:
        root.after_cancel(auto_save_job)
        # Optional: ask if user wants to save *now* if a job was pending?
        # For simplicity, we just cancel and close. Assume recent changes were saved.
    root.destroy()


# ==============================================================================
# --- Main Application Setup ---
# ==============================================================================
root = tk.Tk()
root.title("BGMI Tournament Editor")
root.geometry("700x600")

# --- Status Label (Defined early) ---
status_label = tk.Label(root, text="Initializing...", fg="black", anchor="w")
status_label.pack(side="bottom", fill="x", padx=10, pady=(0, 5))

# --- Load initial data ---
data, soup = load_data()

# --- Treeview Setup ---
tree_frame = tk.Frame(root)
tree_frame.pack(pady=(5, 0), padx=10, fill="both", expand=True)

# Use '#' as the first column name now
display_cols = ("#", "Team", "Points", "Status")
tree = ttk.Treeview(tree_frame, columns=display_cols, show="headings")

col_widths = {"#": 60, "Team": 150, "Points": 70, "Status": 120}
for col in display_cols:
    width = col_widths.get(col, 100)
    tree.heading(col, text=col, anchor="center", command=lambda _col=col: sort_column(tree, _col, False))
    tree.column(col, anchor="center", width=width, stretch=tk.NO if col != "Team" else tk.YES)

vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
vsb.pack(side="right", fill="y")
hsb.pack(side="bottom", fill="x")
tree.pack(side="left", fill="both", expand=True)
tree.bind("<<TreeviewSelect>>", select_entry)

# --- Entry Fields Frame ---
entry_frame = tk.Frame(root)
entry_frame.pack(pady=5, padx=10, fill="x")

# Change Label text from "Rank:" to "#:"
tk.Label(entry_frame, text="#:").grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
rank_var = tk.StringVar()
rank_entry = tk.Entry(entry_frame, textvariable=rank_var, width=8)
rank_entry.grid(row=0, column=1, padx=(0, 10), pady=2, sticky="w")

tk.Label(entry_frame, text="Team:").grid(row=0, column=2, padx=(0, 5), pady=2, sticky="w")
team_var = tk.StringVar()
team_entry = tk.Entry(entry_frame, textvariable=team_var, width=25)
team_entry.grid(row=0, column=3, padx=(0, 10), pady=2, sticky="w")

tk.Label(entry_frame, text="Points:").grid(row=0, column=4, padx=(0, 5), pady=2, sticky="w")
points_var = tk.StringVar()
points_entry = tk.Entry(entry_frame, textvariable=points_var, width=8)
points_entry.grid(row=0, column=5, padx=(0, 10), pady=2, sticky="w")

# --- Status Buttons Frame ---
status_outer_frame = tk.Frame(root)
status_outer_frame.pack(pady=5)
tk.Label(status_outer_frame, text="Status:").pack()
status_buttons_frame = tk.Frame(status_outer_frame)
status_buttons_frame.pack()
status_buttons = []
for i in range(NUM_STATUS_INDICATORS):
    btn = tk.Button(status_buttons_frame, text="❌", width=3, relief=tk.RAISED, command=lambda i=i: toggle_status(i))
    btn.pack(side="left", padx=5, pady=(0,5))
    status_buttons.append(btn)

# --- Action Buttons Frame ---
button_frame = tk.Frame(root)
button_frame.pack(pady=(5, 10), fill="x", side="bottom") # Packed before status label

tk.Button(button_frame, text="Add Entry", command=add_entry).pack(side="left", padx=5, expand=True)
tk.Button(button_frame, text="Update Status", command=update_entry).pack(side="left", padx=5, expand=True)
tk.Button(button_frame, text="Delete Entry", command=delete_entry).pack(side="left", padx=5, expand=True)
# Removed "Save Changes" Button
# tk.Button(button_frame, text="Save Changes", command=perform_save, font=('Helvetica', 9, 'bold')).pack(side="left", padx=5, expand=True) # Manual save still possible if needed
tk.Button(button_frame, text="Clear All", command=clear_all_data, bg="#FF5555", fg="white").pack(side="left", padx=5, expand=True)

# --- Initial Population and Final Setup ---
update_table()
if data: # Apply initial sort only if data exists
    initial_col = sort_column_cache["column"]
    initial_rev = sort_column_cache["reverse"]
    sort_column(tree, initial_col, initial_rev)

# --- Run ---
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()