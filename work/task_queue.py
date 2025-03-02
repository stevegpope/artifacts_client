import os
import json

# Define the file path
TASKS_FILE_PATH = "C:\\Users\\sarah\\Desktop\\code\\artifacts\\work\\tasks\\tasks.txt"

class TaskQueue:
    def __init__(self, file_path=TASKS_FILE_PATH):
        self.file_path = file_path
        # Ensure the file exists
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as file:
                file.write("[]")  # Create an empty JSON array

    def _read_tasks(self):
        """Read all tasks from the file and return them as a list of dictionaries."""
        with open(self.file_path, "r") as file:
            try:
                tasks = json.load(file)  # Deserialize JSON to a list of dictionaries
            except json.JSONDecodeError:
                tasks = []  # If the file is empty or invalid, return an empty list
        return tasks

    def _write_tasks(self, tasks):
        """Write the list of tasks (dictionaries) back to the file as JSON."""
        with open(self.file_path, "w") as file:
            json.dump(tasks, file, indent=4)  # Serialize list of dictionaries to JSON

    def create_task(self, task):
        """Add a new task (dictionary) to the end of the queue."""
        if not isinstance(task, dict):
            raise ValueError("Task must be a dictionary.")
        tasks = self._read_tasks()
        tasks.append(task)
        self._write_tasks(tasks)
        print(f"Task added: {task}")

    def read_tasks(self):
        """Read and return all tasks in the queue."""
        tasks = self._read_tasks()
        return tasks

    def update_task(self, task_index, new_task):
        """Update a task at a specific index."""
        if not isinstance(new_task, dict):
            raise ValueError("Task must be a dictionary.")
        tasks = self._read_tasks()
        if 0 < task_index <= len(tasks):
            tasks[task_index - 1] = new_task
            self._write_tasks(tasks)
            print(f"Task {task_index} updated to: {json.dumps(new_task, indent=4)}")
        else:
            print(f"Invalid task index: {task_index}")

    def delete_task(self, task_index):
        """Delete a task at a specific index."""
        tasks = self._read_tasks()
        if 0 < task_index <= len(tasks):
            deleted_task = tasks.pop(task_index - 1)
            self._write_tasks(tasks)
            print(f"Task deleted: {json.dumps(deleted_task, indent=4)}")
        else:
            print(f"Invalid task index: {task_index}")

    def clear_tasks(self):
        """Clear all tasks from the queue."""
        self._write_tasks([])
        print("All tasks have been cleared.")

# Example usage
if __name__ == "__main__":
    task_queue = TaskQueue()

    # Add tasks (as dictionaries)
    task_queue.create_task({"title": "Write report", "priority": "high", "due_date": "2023-10-15"})
    task_queue.create_task({"title": "Review code", "priority": "medium", "due_date": "2023-10-20"})
    task_queue.create_task({"title": "Fix bugs", "priority": "low", "due_date": "2023-10-25"})

    # Read tasks
    task_queue.read_tasks()

    # Update a task
    task_queue.update_task(2, {"title": "Review and test code", "priority": "high", "due_date": "2023-10-22"})

    # Read tasks after update
    task_queue.read_tasks()

    # Delete a task
    task_queue.delete_task(1)

    # Read tasks after deletion
    task_queue.read_tasks()

    # Clear all tasks
    task_queue.clear_tasks()

    # Read tasks after clearing
    task_queue.read_tasks()