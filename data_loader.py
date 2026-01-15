from pathlib import Path

def read_md_files_from_folder(folder_path):
    """
    Reads all .md files from a single, non-recursive folder.
    """
    md_files_data = []

    # Convert the string path to a Path object
    directory = Path(folder_path)

    # Check if the directory actually exists
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found at: {directory}")

    # Use glob('*.md') to directly get only the markdown files
    for file_path in directory.glob('*.md'):
        try:
            # .read_text() is a convenient way to read a file's content
            content = file_path.read_text(encoding='utf-8')
            
            md_files_data.append({
                'folder_name': directory.name,
                'file_name': file_path.name,
                'content': content
            })
        except Exception as e:
            print(f"Error reading file {file_path.name}: {str(e)}")
            continue

    if not md_files_data:
        raise ValueError(f"No .md files were found in '{directory}'")

    return md_files_data