import shutil
import os
import subprocess

def run_action_delete(files: 'list[str]'):
    for file in files:
        try:
            # Try to unlink first for symlinked directories, so their subcontents don't get deleted
            os.unlink(file)
        except IsADirectoryError:
            shutil.rmtree(file)

def run_action_backup(files: 'list[str]'):
    try:
        # Write files to temporary text file
        with open("backup.txt", "w") as file:
            file.write("\n".join(files))
        subprocess.call(["restic", "-r", "backups-repo", "backup", "--files-from-verbatim", "backup.txt"])
    finally:
        # Clean up temporary text file
        if os.path.exists("backup.txt"): os.unlink("backup.txt")

def run_actions(groups: 'dict[str, list[str]]'):
    for group, files in groups.items():
        print(f"{group:>10}:  {len(files)} items")