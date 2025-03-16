import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# File paths
TASKS_FILE = "tasks.json"
BANNED_ORDER_FILES = [
    "banned_orders_baz.json",
    "banned_orders_baz1.json",
    "banned_orders_baz2.json",
    "banned_orders_baz3.json",
    "banned_orders_baz4.json",
]
CURRENT_ORDER_FILES = [
    "current_orders_baz.json",
    "current_orders_baz1.json",
    "current_orders_baz2.json",
    "current_orders_baz3.json",
    "current_orders_baz4.json",
]

# Load data from JSON files
def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                data = f.read()
                if data.strip():  # Check if the file is not empty
                    return json.loads(data)
        except json.JSONDecodeError:
            print(f"Warning: {file} contains invalid JSON. Resetting to an empty list.")
    return []  # Return an empty list if the file is empty or invalid

# Save data to JSON files
def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# Custom dialog for adding tasks
class AddTaskDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("Add Task")
        self.geometry("300x150")
        self.app = app

        # Role entry
        ttk.Label(self, text="Role:").grid(row=0, column=0, padx=10, pady=10)
        self.role_entry = ttk.Entry(self)
        self.role_entry.grid(row=0, column=1, padx=10, pady=10)

        # Code entry
        ttk.Label(self, text="Code:").grid(row=1, column=0, padx=10, pady=10)
        self.code_entry = ttk.Entry(self)
        self.code_entry.grid(row=1, column=1, padx=10, pady=10)

        # Add button
        ttk.Button(self, text="Add", command=self.on_add).grid(row=2, column=0, columnspan=2, pady=10)

    def on_add(self):
        role = self.role_entry.get()
        code = self.code_entry.get()
        if role and code:
            self.app.add_task(role, code)
            self.destroy()

# File watcher to refresh UI on file changes
class FileWatcher(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_modified(self, event):
        if event.src_path.endswith(".json"):
            self.app.refresh_data()

# Main Application
class TaskManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Manager")
        self.root.geometry("1200x800")

        # Bind the closing event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Store frame references
        self.banned_frame = None
        self.current_frame = None

        # Load data
        self.tasks = load_json(TASKS_FILE)
        self.banned_orders = {file: load_json(file) for file in BANNED_ORDER_FILES}
        self.current_orders = {file: load_json(file) for file in CURRENT_ORDER_FILES}

        # Create sections
        self.create_tasks_section()
        self.create_banned_orders_section()
        self.create_current_orders_section()

        # Start file watcher
        self.event_handler = FileWatcher(self)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, path=".", recursive=False)
        self.observer.start()

    def on_closing(self):
        # Stop the file watcher observer
        self.observer.stop()
        self.observer.join()
        # Close the application
        self.root.destroy()

    def create_tasks_section(self):
        # Frame for tasks
        tasks_frame = ttk.LabelFrame(self.root, text="Tasks", padding="10")
        tasks_frame.pack(fill=tk.X, padx=10, pady=5)

        # Add Task button (moved to the left)
        add_button = ttk.Button(tasks_frame, text="Add Task", command=self.show_add_task_dialog)
        add_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Canvas and scrollbar for tasks
        self.tasks_canvas = tk.Canvas(tasks_frame)
        self.tasks_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tasks_frame, orient=tk.VERTICAL, command=self.tasks_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tasks_canvas.configure(yscrollcommand=scrollbar.set)
        self.tasks_canvas.bind("<Configure>", lambda e: self.tasks_canvas.configure(scrollregion=self.tasks_canvas.bbox("all")))

        # Frame inside canvas
        self.tasks_inner_frame = ttk.Frame(self.tasks_canvas)
        self.tasks_canvas.create_window((0, 0), window=self.tasks_inner_frame, anchor=tk.NW)

        # Render tasks
        self.render_tasks()

    def create_banned_orders_section(self):
        # Destroy the existing frame if it exists
        if self.banned_frame is not None:
            self.banned_frame.destroy()
        
        # Frame for banned orders
        self.banned_frame = ttk.LabelFrame(self.root, text="Banned Orders", padding="10")
        self.banned_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create a horizontal panel for banned orders files
        banned_panel = ttk.PanedWindow(self.banned_frame, orient=tk.HORIZONTAL)
        banned_panel.pack(fill=tk.BOTH, expand=True)

        for file, orders in self.banned_orders.items():
            file_frame = ttk.Frame(banned_panel)
            banned_panel.add(file_frame, weight=1)

            # Label for file name
            ttk.Label(file_frame, text=file).pack(pady=5)

            # Canvas and scrollbar for banned orders
            canvas = tk.Canvas(file_frame)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar = ttk.Scrollbar(file_frame, orient=tk.VERTICAL, command=canvas.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.bind("<Configure>", lambda e, canvas=canvas: canvas.configure(scrollregion=canvas.bbox("all")))

            # Frame inside canvas
            inner_frame = ttk.Frame(canvas)
            canvas.create_window((0, 0), window=inner_frame, anchor=tk.NW)

            # Add orders with remove buttons
            for order in orders:
                frame = ttk.Frame(inner_frame)
                frame.pack(fill=tk.X, pady=2)

                # Order text (handle both string and dict types)
                order_text = order if isinstance(order, str) else json.dumps(order)
                ttk.Label(frame, text=order_text).pack(side=tk.LEFT, padx=5)

                # Remove button
                remove_button = ttk.Button(frame, text="−", command=lambda o=order, f=file: self.remove_banned_order(o, f))
                remove_button.pack(side=tk.RIGHT)

    def create_current_orders_section(self):
        # Destroy the existing frame if it exists
        if self.current_frame is not None:
            self.current_frame.destroy()
                
        # Frame for current orders
        self.current_frame = ttk.LabelFrame(self.root, text="Current Orders", padding="10")
        self.current_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create a horizontal panel for current orders files
        current_panel = ttk.PanedWindow(self.current_frame, orient=tk.HORIZONTAL)
        current_panel.pack(fill=tk.BOTH, expand=True)

        for file, orders in self.current_orders.items():
            file_frame = ttk.Frame(current_panel)
            current_panel.add(file_frame, weight=1)

            # Label for file name
            ttk.Label(file_frame, text=file).pack(pady=5)

            # Canvas and scrollbar for current orders
            canvas = tk.Canvas(file_frame)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar = ttk.Scrollbar(file_frame, orient=tk.VERTICAL, command=canvas.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.bind("<Configure>", lambda e, canvas=canvas: canvas.configure(scrollregion=canvas.bbox("all")))

            # Frame inside canvas
            inner_frame = ttk.Frame(canvas)
            canvas.create_window((0, 0), window=inner_frame, anchor=tk.NW)

            # Add orders with remove buttons (like banned orders section)
            for order in orders:
                frame = ttk.Frame(inner_frame)
                frame.pack(fill=tk.X, pady=2)

                # Order text (handle both string and dict types)
                order_text = order if isinstance(order, str) else json.dumps(order)
                ttk.Label(frame, text=order_text).pack(side=tk.LEFT, padx=5)

                # Remove button
                remove_button = ttk.Button(frame, text="−", command=lambda o=order, f=file: self.remove_current_order(o, f))
                remove_button.pack(side=tk.RIGHT)

    def render_tasks(self):
        # Clear existing tasks
        for widget in self.tasks_inner_frame.winfo_children():
            widget.destroy()

        # Collapse duplicate tasks
        task_counts = defaultdict(int)
        for task in self.tasks:
            key = f"{task['role']} - {task['code']}"
            task_counts[key] += 1

        # Add tasks to the inner frame
        for task, count in task_counts.items():
            frame = ttk.Frame(self.tasks_inner_frame)
            frame.pack(fill=tk.X, pady=2)

            # Task text
            task_text = f"{task} ({count})" if count > 1 else task
            ttk.Label(frame, text=task_text).pack(side=tk.LEFT, padx=5)

            # Remove button
            remove_button = ttk.Button(frame, text="−", command=lambda t=task: self.remove_task(t))
            remove_button.pack(side=tk.RIGHT)

    def show_add_task_dialog(self):
        AddTaskDialog(self.root, self)

    def add_task(self, role, code):
        self.tasks.insert(0, {"role": role, "code": code})  # Add to top
        self.render_tasks()
        save_json(TASKS_FILE, self.tasks)

    def remove_task(self, task):
        # Extract role and code from the task string
        role, code = task.split(" - ")
        self.tasks = [t for t in self.tasks if not (t["role"] == role and t["code"] == code)]
        self.render_tasks()
        save_json(TASKS_FILE, self.tasks)

    def remove_banned_order(self, order, file):
        try:
            # Remove the order from the list
            self.banned_orders[file].remove(order)
            # Save the updated list to the file
            save_json(file, self.banned_orders[file])
        except ValueError:
            # Handle case where item might be represented differently (e.g., string vs dict)
            order_str = json.dumps(order) if not isinstance(order, str) else order
            for item in self.banned_orders[file]:
                item_str = json.dumps(item) if not isinstance(item, str) else item
                if item_str == order_str:
                    self.banned_orders[file].remove(item)
                    save_json(file, self.banned_orders[file])
                    break
        # Re-render the banned orders section
        self.create_banned_orders_section()

    def remove_current_order(self, order, file):
        try:
            # Remove the order from the list
            self.current_orders[file].remove(order)
            # Save the updated list to the file
            save_json(file, self.current_orders[file])
        except ValueError:
            # Handle case where item might be represented differently (e.g., string vs dict)
            order_str = json.dumps(order) if not isinstance(order, str) else order
            for item in self.current_orders[file]:
                item_str = json.dumps(item) if not isinstance(item, str) else item
                if item_str == order_str:
                    self.current_orders[file].remove(item)
                    save_json(file, self.current_orders[file])
                    break
        # Re-render the current orders section
        self.create_current_orders_section()

    def refresh_data(self):
        # Reload data from files
        self.tasks = load_json(TASKS_FILE)
        self.banned_orders = {file: load_json(file) for file in BANNED_ORDER_FILES}
        self.current_orders = {file: load_json(file) for file in CURRENT_ORDER_FILES}

        # Re-render UI
        self.render_tasks()
        self.create_banned_orders_section()
        self.create_current_orders_section()

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = TaskManagerApp(root)
    root.mainloop()