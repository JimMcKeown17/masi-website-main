import os

# Set the root directory of your Django project
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))  # Change to your project's path if needed
OUTPUT_FILE = "llm_review_short.txt"
EXTENSIONS = {".html", ".css", ".js"}  # Add more as needed

def collect_code_files(root_dir, extensions):
    """ Walk through project directory and collect code files. """
    code_files = []
    
    for foldername, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(tuple(extensions)):
                filepath = os.path.join(foldername, filename)
                code_files.append(filepath)
    
    return code_files

def write_combined_file(file_list, output_file):
    """ Write all files into a single document, separated by headers. """
    with open(output_file, "w", encoding="utf-8") as out_file:
        for filepath in file_list:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                # Write a separator for each file
                out_file.write(f"\n### {filepath} ###\n")
                out_file.write(content)
                out_file.write("\n\n")
            except Exception as e:
                print(f"Skipping {filepath} due to error: {e}")

if __name__ == "__main__":
    print(f"Scanning directory: {ROOT_DIR}")
    code_files = collect_code_files(ROOT_DIR, EXTENSIONS)
    print(f"Found {len(code_files)} code files.")
    
    write_combined_file(code_files, OUTPUT_FILE)
    print(f"Code exported to {OUTPUT_FILE}. Ready for LLM review!")
