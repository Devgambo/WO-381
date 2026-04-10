import re
from pathlib import Path

def chunk_ocr_file(content: str, file_name: str) -> list[dict]:
    """Section-aware splitter for OCR files."""
    sections = re.split(r'(?m)^(#{1,4}\s+.*$)', content)
    
    chunks = []
    current_title = ""
    current_section = ""
    clause_id = ""
    
    # sections[0] is text before any heading
    if sections and sections[0].strip():
        curr_text = sections[0].strip()
        if len(curr_text) > 100:
            chunks.append({
                "source_file": file_name,
                "section_number": "Prelim",
                "section_title": "Preliminary",
                "clause_id": "",
                "content_type": "text",
                "content": curr_text
            })

    for i in range(1, len(sections), 2):
        heading = sections[i]
        text_block = sections[i+1]
        
        heading_clean = heading.strip('#').strip()
        
        sec_match = re.search(r'SECTION\s+(\d+)', heading_clean, re.IGNORECASE)
        if sec_match:
            current_section = sec_match.group(1)
            current_title = heading_clean
            clause_id = ""
        else:
            clause_match = re.match(r'^([\d\.]+)\s+(.*)', heading_clean)
            if clause_match:
                clause_id = clause_match.group(1)
                current_title = clause_match.group(2)
            else:
                clause_id = ""
                current_title = heading_clean
                
        paragraphs = [p.strip() for p in text_block.split('\n\n') if p.strip()]
        
        temp_chunk = ""
        for p in paragraphs:
            if len(temp_chunk) + len(p) > 1500:
                if len(temp_chunk) > 100:
                    chunks.append({
                        "source_file": file_name,
                        "section_number": current_section,
                        "section_title": current_title,
                        "clause_id": clause_id,
                        "content_type": "text",
                        "content": heading.strip() + "\n\n" + temp_chunk
                    })
                temp_chunk = p
            else:
                temp_chunk += "\n\n" + p if temp_chunk else p
                
        if len(temp_chunk) > 100:
            chunks.append({
                "source_file": file_name,
                "section_number": current_section,
                "section_title": current_title,
                "clause_id": clause_id,
                "content_type": "text",
                "content": heading.strip() + "\n\n" + temp_chunk
            })

    return chunks

def parse_images_tables(content: str, file_name: str) -> list[dict]:
    """Parser for the cleaned SP_IMAGES_TABLES.md (markdown section format).
    
    The cleaned file has entries like:
        ## is_code_chunk_014 (TABLE, Page 0)
        <description text>
        
        **Symbols & Notation:**
        | Symbol | Meaning | Unit |
        ...
        ---
    """
    chunks = []
    # Split on section headers that look like: ## is_code_chunk_NNN (...)
    sections = re.split(r'(?m)^##\s+(is_code_chunk_\d+)\s*\(([^)]*)\)', content)
    
    # sections[0] is the preamble (title, description, first ---)
    # Then pairs of: [chunk_id, header_info, body_text]
    for i in range(1, len(sections), 3):
        if i + 2 >= len(sections):
            break
            
        chunk_id = sections[i].strip()
        header_info = sections[i + 1].strip()  # e.g. "DIAGRAM, Page 0"
        body = sections[i + 2].strip()
        
        # Parse data_type and page from header
        header_parts = [p.strip() for p in header_info.split(',')]
        data_type = header_parts[0] if header_parts else "UNKNOWN"
        page = ""
        for hp in header_parts:
            if hp.startswith("Page"):
                page = hp.replace("Page", "").strip()
        
        # Determine content type
        data_type_upper = data_type.upper()
        if "TABLE" in data_type_upper:
            c_type = "table"
        elif "DIAGRAM" in data_type_upper:
            c_type = "image_description"
        else:
            c_type = "text"
        
        # Extract symbols from embedded table if present
        symbols = []
        sym_match = re.search(r'\*\*Symbols & Notation:\*\*\s*\n\|[^\n]+\n\|[-|]+\n((?:\|[^\n]+\n)*)', body)
        if sym_match:
            for row in sym_match.group(1).strip().splitlines():
                cols = [c.strip() for c in row.split('|')]
                cols = [c for c in cols if c]  # remove empty
                if len(cols) >= 2:
                    symbols.append(f"{cols[0]} ({cols[1]}, {cols[2] if len(cols) > 2 else ''})")
        
        sym_str = ", ".join(symbols)
        
        # For the chunk content, use the full body (including symbol table)
        # This ensures the embedding captures everything
        chunks.append({
            "chunk_id": chunk_id,
            "source_file": file_name,
            "data_type": data_type,
            "content_type": c_type,
            "page": page,
            "symbols": sym_str,
            "content": body
        })

    return chunks

def chunk_guide_file(content: str, file_name: str) -> list[dict]:
    """Step-based splitter for RCC guides."""
    element_type = "beam" if "beam" in file_name.lower() else "column" if "column" in file_name.lower() else "guide"
    
    sections = re.split(r'(?m)^(##?\s+(?:Step|STEP|\d+\.).*$)', content)
    
    chunks = []
    
    if sections and sections[0].strip():
        if len(sections[0].strip()) > 100:
            chunks.append({
                "source_file": file_name,
                "content_type": "procedural_guide",
                "element_type": element_type,
                "step_number": "Prelim",
                "content": sections[0].strip()
            })
            
    for i in range(1, len(sections), 2):
        heading = sections[i]
        text_block = sections[i+1].strip()
        step_match = re.search(r'(?:Step|STEP|\d+\.)\s*(\d*)', heading)
        step_idx = step_match.group(1) if step_match and step_match.group(1) else heading.strip('# ')
        
        full_content = heading + "\n\n" + text_block
        if len(full_content) > 50:
            chunks.append({
                "source_file": file_name,
                "content_type": "procedural_guide",
                "element_type": element_type,
                "step_number": step_idx,
                "content": full_content
            })
            
    return chunks

def read_md_files_from_folder(folder_path: str) -> list[dict]:
    """Reads and chunks all .md files using specialized parsers."""
    directory = Path(folder_path)
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found at: {directory}")

    all_chunks = []
    
    for file_path in directory.glob('*.md'):
        try:
            content = file_path.read_text(encoding='utf-8')
            file_name = file_path.name
            
            if file_name.startswith('SP_34_OCR_'):
                file_chunks = chunk_ocr_file(content, file_name)
            elif file_name == 'SP_IMAGES_TABLES.md':
                file_chunks = parse_images_tables(content, file_name)
            elif file_name.startswith('Reading_RCC_'):
                file_chunks = chunk_guide_file(content, file_name)
            else:
                # Fallback
                file_chunks = [{
                    "source_file": file_name, 
                    "content_type": "text", 
                    "content": content
                }]
                
            all_chunks.extend(file_chunks)
        except Exception as e:
            print(f"Error reading file {file_path.name}: {str(e)}")
            continue

    if not all_chunks:
        raise ValueError(f"No valid chunks parsed from '{directory}'")

    return all_chunks