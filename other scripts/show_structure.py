import os
import sys

def show_structure(parent_path, indent=0):
    """Recursively print folder and file structure."""
    try:
        items = sorted(os.listdir(parent_path))
    except PermissionError:
        print(" " * indent + f"[Permission Denied]: {parent_path}")
        return
    except FileNotFoundError:
        print(" " * indent + f"[Not Found]: {parent_path}")
        return

    for item in items:
        item_path = os.path.join(parent_path, item)
        prefix = " " * indent + ("├── " if indent else "")
        if os.path.isdir(item_path):
            print(f"{prefix}{item}/")
            show_structure(item_path, indent + 4)
        else:
            print(f"{prefix}{item}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python show_structure.py <parent_directory>")
        sys.exit(1)

    parent_dir = sys.argv[1]
    if not os.path.exists(parent_dir):
        print(f"Error: The directory '{parent_dir}' does not exist.")
        sys.exit(1)

    print(f"\nFolder structure for: {parent_dir}\n")
    show_structure(parent_dir)
