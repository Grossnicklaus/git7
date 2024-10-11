import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, PhotoImage
import psutil
import concurrent.futures
import queue
import subprocess
from win32com.client import Dispatch

def search_large_folders(directory, result_queue, progress_var):
    total_dirs = sum(len(dirs) for _, dirs, _ in os.walk(directory))
    processed_dirs = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for root, dirs, _ in os.walk(directory):
            for name in dirs:
                folder_path = os.path.join(root, name)
                futures.append(executor.submit(process_folder, folder_path, result_queue))
                processed_dirs += 1
                progress_var.set((processed_dirs / total_dirs) * 100)
        concurrent.futures.wait(futures)

def process_folder(folder_path, result_queue):
    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        total_size_mb = total_size / (1024 * 1024)  # Size in MB
        if total_size_mb > 500:
            result_queue.put((folder_path, total_size_mb))
    except (PermissionError, FileNotFoundError):
        pass

def update_treeview(result_queue):
    items = []
    while True:
        try:
            path, size = result_queue.get(timeout=1)
            items.append((path, size))
            items.sort(key=lambda x: x[1], reverse=True)  # Sort items by size in descending order
            tree.delete(*tree.get_children())  # Clear previous results
            for path, size in items:
                tree.insert("", "end", values=(path, f"{size:.2f} MB"))
        except queue.Empty:
            if search_thread is None or not search_thread.is_alive():
                break

def on_search():
    global search_thread
    directory = drive_combobox.get() or "C:\\"
    tree.delete(*tree.get_children())  # Clear previous results
    result_queue = queue.Queue()
    progress_var.set(0)
    search_thread = threading.Thread(target=search_large_folders, args=(directory, result_queue, progress_var))
    search_thread.start()
    update_thread = threading.Thread(target=update_treeview, args=(result_queue,))
    update_thread.start()

def on_browse():
    directory = filedialog.askdirectory()
    if directory:
        drive_combobox.set(directory)

def on_open_explorer(path):
    subprocess.run(["explorer", path])

def on_delete(path):
    try:
        if messagebox.askyesno("Delete", f"Are you sure you want to delete {path}?"):
            if os.path.isdir(path):
                os.rmdir(path)
            elif os.path.isfile(path):
                os.remove(path)
            tree.delete(tree.selection())
            messagebox.showinfo("Deleted", f"{path} has been deleted.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete {path}: {e}")

def on_right_click(event):
    selected_item = tree.identify_row(event.y)
    if selected_item:
        tree.selection_set(selected_item)
        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label="Open in Explorer", command=lambda: on_open_explorer(tree.item(selected_item)['values'][0]))
        menu.add_command(label="Delete", command=lambda: on_delete(tree.item(selected_item)['values'][0]))
        menu.post(event.x_root, event.y_root)

def create_shortcut():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    path = os.path.join(desktop, "Large Folder Finder.lnk")

    if getattr(sys, 'frozen', False):
        working_directory = sys._MEIPASS
        icon_path = os.path.join(working_directory, "logo.ico")
    else:
        working_directory = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(working_directory, "logo.ico")

    if not os.path.exists(icon_path):
        print(f"Icon file not found at {icon_path}. Please make sure it exists.")
        return

    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortcut(path)
    shortcut.TargetPath = sys.executable
    shortcut.WorkingDirectory = working_directory
    shortcut.IconLocation = icon_path
    shortcut.Description = "Shortcut for Large Folder Finder Application"
    shortcut.save()

    print(f"Shortcut created successfully at {path}")

def make_draggable(widget):
    def on_drag_start(event):
        widget.startX = event.x
        widget.startY = event.y

    def on_drag_motion(event):
        x = widget.winfo_x() - widget.startX + event.x
        y = widget.winfo_y() - widget.startY + event.y
        x = max(0, min(root.winfo_screenwidth() - root.winfo_width(), x))
        y = max(0, min(root.winfo_screenheight() - root.winfo_height(), y))
        root.geometry(f"+{x}+{y}")

    widget.bind("<Button-1>", on_drag_start)
    widget.bind("<B1-Motion>", on_drag_motion)

def close_app():
    if search_thread is not None and search_thread.is_alive():
        search_thread.join(timeout=1)
    root.destroy()

root = tk.Tk()
root.title("Large Folder Finder")
root.geometry("800x600")
root.overrideredirect(True)
make_draggable(root)

if getattr(sys, 'frozen', False):
    working_directory = sys._MEIPASS
    icon_path = os.path.join(working_directory, "logo.ico")
else:
    working_directory = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(working_directory, "logo.ico")

if os.path.exists(icon_path):
    root.iconbitmap(icon_path)
else:
    print(f"Icon file not found at {icon_path}. Please make sure it exists.")

logo_path = os.path.join(working_directory, "logo.png")
if os.path.exists(logo_path):
    logo_photo = PhotoImage(file=logo_path)
    logo_label = tk.Label(root, image=logo_photo, bg="#f0f0f0")
    logo_label.place(x=10, y=10)
else:
    print(f"Logo file not found at {logo_path}. Please make sure it exists.")

close_button = tk.Button(root, text="✖", command=close_app, bg="#f44336", fg="white", font=("Arial", 12, "bold"), relief=tk.FLAT)
close_button.place(relx=0.98, rely=0.02, anchor=tk.NE)

frame = tk.Frame(root)
frame.pack(pady=10)

tk.Label(frame, text="Select Drive or Folder:").pack(side=tk.LEFT, padx=5)
drive_combobox = ttk.Combobox(frame)
drives = [f"{d.mountpoint}" for d in psutil.disk_partitions() if 'fixed' in d.opts.lower()]
drive_combobox['values'] = drives
drive_combobox.set("C:\\")
drive_combobox.pack(side=tk.LEFT, padx=5)

browse_button = tk.Button(frame, text="Browse", command=on_browse)
browse_button.pack(side=tk.LEFT, padx=5)

search_button = tk.Button(root, text="Search", command=on_search)
search_button.pack(pady=10)

tree_frame = tk.Frame(root)
tree_frame.pack(fill=tk.BOTH, expand=True)

tree_scroll = tk.Scrollbar(tree_frame)
tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

tree = ttk.Treeview(tree_frame, columns=("Path", "Size"), yscrollcommand=tree_scroll.set, show="headings")
tree.heading("Path", text="Path")
tree.heading("Size", text="Size")
tree.column("Path", width=600, anchor=tk.W)
tree.column("Size", width=100, anchor=tk.E)
tree.pack(fill=tk.BOTH, expand=True)

tree_scroll.config(command=tree.yview)

tree.bind("<Button-3>", on_right_click)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
progress_bar.place(relx=0.977, rely=1, anchor=tk.SE, width=150)

create_shortcut()

search_thread = None
root.mainloop()