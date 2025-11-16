#!/usr/bin/env python3
"""Remove all logger.info statements containing DEBUG: while preserving indentation"""
import re
import sys

def remove_debug_logger_statements(file_path):
    """Remove all logger.info statements containing DEBUG: from a file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    removed_count = 0
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a logger.info line with DEBUG:
        if re.search(r'logger\.info\([^)]*DEBUG:', line):
            # Check if it's a multi-line statement
            if line.rstrip().endswith('\\') or ('f"' in line and line.count('"') == 1):
                # Multi-line statement - skip until we find the closing
                removed_count += 1
                i += 1
                # Skip continuation lines
                while i < len(lines) and (lines[i].strip().startswith('f"') or lines[i].strip().endswith('\\')):
                    i += 1
                # Skip the closing line
                if i < len(lines):
                    i += 1
                continue
            else:
                # Single line logger.info with DEBUG:
                removed_count += 1
                i += 1
                continue
        
        new_lines.append(line)
        i += 1
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Removed {removed_count} DEBUG logger.info statements from {file_path}")
    return removed_count

if __name__ == "__main__":
    files = [
        "src/index.py",
        "src/services/s3_service.py"
    ]
    
    total_removed = 0
    for file_path in files:
        try:
            removed = remove_debug_logger_statements(file_path)
            total_removed += removed
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\nTotal DEBUG logger.info statements removed: {total_removed}")

