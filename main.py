import os
import time
import streamlit as st
import re
from llm_handler import analyze_rcc_drawing, analyze_rcc_drawing_from_images
from prompt import INITIAL_EXTRACTION_PROMPT, REFINEMENT_PROMPT_TEMPLATE
from embedding_service import embedding_model
from vector_db import VectorStore
from llm_service import generate_compliance_report
from PIL import Image

# --- Configuration ---
REPORTS_DIR = "reports"
UPLOADS_DIR = "uploads"
IMAGES_DIR = "uploads"  # Store images in the same uploads directory
FIRST_EXTRACT_DIR = "first_extract"
RESULT_DIR = "RESULT"
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(FIRST_EXTRACT_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# Initialize vector DB (assuming it's already populated)
vectordb = VectorStore(collection_name="is_codes_docs", folder_path="./chroma_db")

def markdown_to_pdf(markdown_text: str, output_path: str):
    """
    Converts markdown text to PDF using markdown + weasyprint.
    Falls back to reportlab if weasyprint fails (better Windows support).
    Returns (success: bool, error_message: str or None)
    """
    # Try WeasyPrint first
    try:
        import markdown
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        
        # Convert markdown to HTML
        html_content = markdown.markdown(markdown_text, extensions=['tables', 'fenced_code'])
        
        # Create full HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    line-height: 1.6;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                code {{
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Generate PDF
        font_config = FontConfiguration()
        HTML(string=full_html).write_pdf(output_path, font_config=font_config)
        return True, None
    except ImportError:
        # WeasyPrint not installed, try reportlab
        pass
    except Exception as e:
        # WeasyPrint installed but failed (e.g., GTK libraries missing on Windows)
        error_msg = str(e)
        if 'libgobject' in error_msg.lower() or 'gtk' in error_msg.lower() or 'cannot load library' in error_msg.lower():
            # Try fallback with reportlab (better Windows support)
            pass
        else:
            # Other WeasyPrint errors - try reportlab anyway
            pass
    
    # Try fallback with reportlab (better Windows support)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        import html
        
        # Create PDF
        doc = SimpleDocTemplate(output_path, pagesize=letter, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        story = []
        
        # Define custom styles
        h1_style = ParagraphStyle(
            'H1',
            parent=styles['Heading1'],
            fontSize=12,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=6,
            spaceBefore=6,
        )
        
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            fontSize=10,
            textColor=colors.HexColor('#2a2a2a'),
            spaceAfter=5,
            spaceBefore=5,
        )
        
        h3_style = ParagraphStyle(
            'H3',
            parent=styles['Heading3'],
            fontSize=9,
            textColor=colors.HexColor('#3a3a3a'),
            spaceAfter=4,
            spaceBefore=4,
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            spaceAfter=3,
        )
        
        # Helper function to convert markdown inline formatting to reportlab XML
        def convert_inline_formatting(text):
            # Escape HTML first
            text = html.escape(text)
            # Convert markdown to reportlab XML
            # Bold: **text** or __text__ (process before italic to avoid conflicts)
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
            # Code: `text` (process before italic)
            text = re.sub(r'`(.+?)`', r'<font name="Courier" color="darkblue">\1</font>', text)
            # Italic: *text* (single asterisk, not double)
            # Match *text* but not **text** (already processed)
            text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', text)
            # Italic: _text_ (single underscore, not double)
            text = re.sub(r'(?<!_)_([^_]+?)_(?!_)', r'<i>\1</i>', text)
            return text
        
        # Helper function to parse markdown table
        def parse_table(lines, start_idx):
            """Parse a markdown table starting at start_idx. Returns (table_data, end_idx)"""
            table_data = []
            i = start_idx
            
            # Read header
            if i >= len(lines) or not lines[i].strip().startswith('|'):
                return None, start_idx
            
            header_line = lines[i].strip()
            if not header_line.startswith('|') or not header_line.endswith('|'):
                return None, start_idx
            
            headers = [cell.strip() for cell in header_line.split('|')[1:-1]]
            i += 1
            
            # Skip separator row (|---|---|)
            if i < len(lines) and re.match(r'^\|[\s\-:]+$', lines[i].strip()):
                i += 1
            
            # Read data rows
            while i < len(lines):
                row_line = lines[i].strip()
                if not row_line.startswith('|'):
                    break
                
                cells = [cell.strip() for cell in row_line.split('|')[1:-1]]
                if len(cells) == len(headers):
                    table_data.append(cells)
                i += 1
            
            if table_data:
                return [headers] + table_data, i
            return None, start_idx
        
        # Parse markdown line by line
        lines = markdown_text.split('\n')
        i = 0
        in_list = False
        list_items = []
        
        while i < len(lines):
            line = lines[i].rstrip()
            
            # Empty line
            if not line.strip():
                if in_list and list_items:
                    # Add list items
                    for item in list_items:
                        bullet_text = convert_inline_formatting(item)
                        story.append(Paragraph(f"• {bullet_text}", normal_style))
                    list_items = []
                    in_list = False
                story.append(Spacer(1, 0.1*inch))
                i += 1
                continue
            
            # Tables (check before headers to avoid conflicts)
            if line.strip().startswith('|') and '|' in line[1:]:
                table_data, new_idx = parse_table(lines, i)
                if table_data:
                    # Create table
                    table_style = TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#000000')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 7),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                        ('TOPPADDING', (0, 0), (-1, 0), 6),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                        ('TOPPADDING', (0, 1), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                    ])
                    
                    # Convert table data to Paragraphs with formatting
                    formatted_table_data = []
                    for row_idx, row in enumerate(table_data):
                        formatted_row = []
                        for cell in row:
                            formatted_cell = Paragraph(convert_inline_formatting(cell), normal_style)
                            formatted_row.append(formatted_cell)
                        formatted_table_data.append(formatted_row)
                    
                    # Create table with auto column widths
                    # Calculate available width (page width minus margins)
                    available_width = letter[0] - 144  # 72*2 for left and right margins
                    col_widths = [available_width / len(table_data[0])] * len(table_data[0])
                    pdf_table = Table(formatted_table_data, colWidths=col_widths)
                    pdf_table.setStyle(table_style)
                    story.append(pdf_table)
                    story.append(Spacer(1, 0.15*inch))
                    i = new_idx
                    continue
            
            # Headers
            if line.startswith('#'):
                if in_list and list_items:
                    for item in list_items:
                        bullet_text = convert_inline_formatting(item)
                        story.append(Paragraph(f"• {bullet_text}", normal_style))
                    list_items = []
                    in_list = False
                
                if line.startswith('###'):
                    header_text = convert_inline_formatting(line[3:].strip())
                    story.append(Paragraph(header_text, h3_style))
                elif line.startswith('##'):
                    header_text = convert_inline_formatting(line[2:].strip())
                    story.append(Paragraph(header_text, h2_style))
                elif line.startswith('#'):
                    header_text = convert_inline_formatting(line[1:].strip())
                    story.append(Paragraph(header_text, h1_style))
                i += 1
                continue
            
            # Horizontal rule - just add spacing, don't render dashes
            if re.match(r'^---+$|^===+$|^\*\*\*+$', line):
                story.append(Spacer(1, 0.15*inch))
                i += 1
                continue
            
            # Unordered list
            if re.match(r'^[-*+]\s+', line):
                in_list = True
                item_text = re.sub(r'^[-*+]\s+', '', line)
                list_items.append(item_text)
                i += 1
                continue
            
            # Ordered list
            if re.match(r'^\d+\.\s+', line):
                if in_list and list_items:
                    for item in list_items:
                        bullet_text = convert_inline_formatting(item)
                        story.append(Paragraph(f"• {bullet_text}", normal_style))
                    list_items = []
                    in_list = False
                item_text = re.sub(r'^\d+\.\s+', '', line)
                item_text = convert_inline_formatting(item_text)
                story.append(Paragraph(item_text, normal_style))
                i += 1
                continue
            
            # Regular paragraph
            if in_list and list_items:
                for item in list_items:
                    bullet_text = convert_inline_formatting(item)
                    story.append(Paragraph(f"• {bullet_text}", normal_style))
                list_items = []
                in_list = False
            
            # Convert inline formatting and add paragraph
            formatted_text = convert_inline_formatting(line)
            story.append(Paragraph(formatted_text, normal_style))
            i += 1
        
        # Handle any remaining list items
        if in_list and list_items:
            for item in list_items:
                bullet_text = convert_inline_formatting(item)
                story.append(Paragraph(f"• {bullet_text}", normal_style))
        
        doc.build(story)
        return True, None
    except ImportError:
        return False, "PDF conversion requires either 'weasyprint' or 'reportlab'. Install with: `pip install weasyprint` or `pip install reportlab`"
    except Exception as e:
        return False, f"PDF conversion failed with reportlab: {str(e)}"
    
    # If we get here, both methods failed
    return False, "PDF conversion requires either 'weasyprint' (with GTK+ libraries) or 'reportlab'. For Windows, install reportlab: `pip install reportlab`"


# Streamlit UI
st.set_page_config(
    page_title="Foundation compliance check using AI",
    page_icon="🧑‍🔬",
    layout="wide"
)

st.title("🧑‍🔬 Foundation compliance check using AI")
st.markdown("Analyze Structural drawings for compliance with IS 456:2000 and SP 34")

# Initialize session state
if 'initial_report' not in st.session_state:
    st.session_state.initial_report = None
if 'final_report' not in st.session_state:
    st.session_state.final_report = None
if 'pdf_filename' not in st.session_state:
    st.session_state.pdf_filename = None
if 'uploaded_images' not in st.session_state:
    st.session_state.uploaded_images = None
if 'image_names' not in st.session_state:
    st.session_state.image_names = None
if 'file_type' not in st.session_state:
    st.session_state.file_type = None  # 'pdf' or 'image'

# Section 1: File Upload and Initial Report Generation
st.header("📄 Step 1: Upload PDF or Image and Generate Initial Report")

# Create tabs for PDF and Image upload
upload_tab1, upload_tab2 = st.tabs(["📄 Upload PDF", "🖼️ Upload Image"])

with upload_tab1:
    uploaded_file = st.file_uploader(
        "Upload a PDF file",
        type=['pdf'],
        help="Upload an RCC structural drawing PDF for analysis",
        key="pdf_uploader"
    )

    if uploaded_file is not None:
        # Save uploaded file
        pdf_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.session_state.pdf_filename = uploaded_file.name
        st.session_state.file_type = 'pdf'
        st.session_state.uploaded_images = None  # Clear image state
        st.session_state.image_names = None  # Clear image names
        st.success(f"✅ PDF uploaded: {uploaded_file.name}")

        # Generate initial report button
        if st.button("🔍 Generate Initial Report", type="primary", key="generate_pdf_report"):
            with st.spinner("Analyzing PDF and generating initial compliance report..."):
                try:
                    initial_report = analyze_rcc_drawing(pdf_path, INITIAL_EXTRACTION_PROMPT)
                    st.session_state.initial_report = initial_report
                    
                    # Save the initial report
                    timestamp = int(time.time())
                    initial_filename = f"initial_report_{os.path.basename(uploaded_file.name)}_{timestamp}.md"
                    initial_filepath = os.path.join(FIRST_EXTRACT_DIR, initial_filename)
                    with open(initial_filepath, 'w', encoding='utf-8') as f:
                        f.write(initial_report)
                    
                    st.success("✅ Initial report generated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error during analysis: {e}")

with upload_tab2:
    uploaded_images = st.file_uploader(
        "Upload image file(s)",
        type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'],
        help="Upload RCC structural drawing image(s) for analysis. You can upload multiple images.",
        accept_multiple_files=True,
        key="image_uploader"
    )

    if uploaded_images is not None and len(uploaded_images) > 0:
        # Process and save uploaded images
        pil_images = []
        image_names = []
        
        for uploaded_image in uploaded_images:
            # Save uploaded image
            image_path = os.path.join(IMAGES_DIR, uploaded_image.name)
            with open(image_path, "wb") as f:
                f.write(uploaded_image.getbuffer())
            
            # Convert to PIL Image
            try:
                pil_image = Image.open(uploaded_image)
                # Convert to RGB if necessary (for formats like PNG with transparency)
                if pil_image.mode in ('RGBA', 'LA', 'P'):
                    pil_image = pil_image.convert('RGB')
                pil_images.append(pil_image)
                image_names.append(uploaded_image.name)
            except Exception as e:
                st.error(f"❌ Error processing image {uploaded_image.name}: {e}")
                continue
        
        if pil_images:
            st.session_state.uploaded_images = pil_images
            st.session_state.image_names = image_names
            st.session_state.pdf_filename = ", ".join(image_names) if len(image_names) > 1 else image_names[0]
            st.session_state.file_type = 'image'
            
            # Display uploaded images
            st.success(f"✅ {len(pil_images)} image(s) uploaded successfully!")
            cols = st.columns(min(3, len(pil_images)))
            for idx, (img, name) in enumerate(zip(pil_images, image_names)):
                with cols[idx % 3]:
                    st.image(img, caption=name, use_container_width=True)

    # Generate initial report button (show if images are available in session state)
    if st.session_state.uploaded_images:
        if st.button("🔍 Generate Initial Report", type="primary", key="generate_image_report"):
            with st.spinner("Analyzing image(s) and generating initial compliance report..."):
                try:
                    initial_report = analyze_rcc_drawing_from_images(
                        st.session_state.uploaded_images, 
                        INITIAL_EXTRACTION_PROMPT
                    )
                    st.session_state.initial_report = initial_report
                    
                    # Save the initial report
                    timestamp = int(time.time())
                    # Use stored image names or fallback to pdf_filename
                    img_names = st.session_state.image_names if st.session_state.image_names else [st.session_state.pdf_filename] if st.session_state.pdf_filename else ["image"]
                    image_name_str = "_".join([os.path.splitext(name)[0] for name in img_names[:3]])
                    if len(img_names) > 3:
                        image_name_str += f"_and_{len(img_names)-3}_more"
                    initial_filename = f"initial_report_{image_name_str}_{timestamp}.md"
                    initial_filepath = os.path.join(FIRST_EXTRACT_DIR, initial_filename)
                    with open(initial_filepath, 'w', encoding='utf-8') as f:
                        f.write(initial_report)
                    
                    st.success("✅ Initial report generated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error during analysis: {e}")

# Display Full Initial Report
if st.session_state.initial_report:
    st.header("📋 Step 2: Initial Compliance Report")
    st.markdown("---")
    st.markdown(st.session_state.initial_report)
    st.markdown("---")
    init_col1, init_col2 = st.columns(2)

    with init_col1:
        initial_md_filename = f"initial_compliance_report_{int(time.time())}.md"
        st.download_button(
            label="📥 Download Initial Report as Markdown",
            data=st.session_state.initial_report,
            file_name=initial_md_filename,
            mime="text/markdown"
        )

    with init_col2:
        initial_pdf_filename = f"initial_compliance_report_{int(time.time())}.pdf"
        initial_pdf_path = os.path.join(REPORTS_DIR, initial_pdf_filename)

        try:
            pdf_success, error_msg = markdown_to_pdf(st.session_state.initial_report, initial_pdf_path)
            if pdf_success and os.path.exists(initial_pdf_path):
                with open(initial_pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="📄 Download Initial Report as PDF",
                        data=pdf_file.read(),
                        file_name=initial_pdf_filename,
                        mime="application/pdf"
                    )
            else:
                if error_msg:
                    st.info(f"💡 {error_msg}")
                else:
                    st.info("💡 PDF conversion requires 'weasyprint' or 'reportlab'. Install with: `pip install weasyprint` or `pip install reportlab`")
        except Exception as e:
            st.info(f"💡 PDF conversion not available. Error: {e}")
    
    # Section 3: User Input
    st.header("✏️ Step 3: Provide Additional Information")
    st.markdown("Please provide any missing information or corrections:")
    
    user_provided_info = st.text_area(
        "User Input",
        height=150,
        placeholder="Example:\nsite - mangalore, karnataka\nsevere condition to be taken\ntake limiting value for rest missing information",
        help="Enter any additional information that addresses the missing or wrong information items"
    )
    
    # Section 4: Generate Final Report
    if st.button("🚀 Generate Final Report", type="primary"):
        if not user_provided_info.strip():
            st.warning("⚠️ Please provide additional information before generating the final report.")
        else:
            with st.spinner("Generating final compliance report with RAG-enhanced analysis..."):
                try:
                    refinement_prompt = REFINEMENT_PROMPT_TEMPLATE.format(
                        previous_analysis=st.session_state.initial_report,
                        user_input=user_provided_info
                    )
                    
                    final_report = generate_compliance_report(
                        vectordb=vectordb,
                        embedding_model=embedding_model,
                        Initial_report=refinement_prompt,
                        previous_analysis=st.session_state.initial_report,
                        user_input=user_provided_info,
                    )
                    
                    st.session_state.final_report = final_report
                    
                    # Save final report to RESULT folder
                    timestamp = int(time.time())
                    if st.session_state.file_type == 'pdf' and st.session_state.pdf_filename:
                        base_name = os.path.basename(st.session_state.pdf_filename)
                    elif st.session_state.file_type == 'image' and st.session_state.pdf_filename:
                        base_name = st.session_state.pdf_filename.replace(", ", "_").replace(" ", "_")
                    else:
                        base_name = "unknown"
                    final_filename = f"final_report_{base_name}_{timestamp}.md"
                    final_filepath = os.path.join(RESULT_DIR, final_filename)
                    with open(final_filepath, 'w', encoding='utf-8') as f:
                        f.write(final_report)
                    
                    st.success(f"✅ Final report generated and saved to {final_filepath}!")
                except Exception as e:
                    st.error(f"❌ Error generating final report: {e}")

# Display Final Report
if st.session_state.final_report:
    st.header("📊 Step 4: Final Compliance Report")
    st.markdown("---")
    
    # Display the report
    st.markdown(st.session_state.final_report)
    
    # Download button
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        # Download as Markdown
        st.download_button(
            label="📥 Download Final Report as Markdown",
            data=st.session_state.final_report,
            file_name=f"compliance_report_{int(time.time())}.md",
            mime="text/markdown"
        )
    
    with col2:
        # Download as PDF
        timestamp = int(time.time())
        pdf_filename = f"compliance_report_{timestamp}.pdf"
        pdf_path = os.path.join(REPORTS_DIR, pdf_filename)
        
        # Try to convert to PDF
        try:
            pdf_success, error_msg = markdown_to_pdf(st.session_state.final_report, pdf_path)
            if pdf_success and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="📄 Download Final Report as PDF",
                        data=pdf_file.read(),
                        file_name=pdf_filename,
                        mime="application/pdf"
                    )
            else:
                if error_msg:
                    st.info(f"💡 {error_msg}")
                else:
                    st.info("💡 PDF conversion requires 'weasyprint' or 'reportlab'. Install with: `pip install weasyprint` or `pip install reportlab`")
        except Exception as e:
            st.info(f"💡 PDF conversion not available. Error: {e}")

# Sidebar information
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This tool analyzes RCC structural drawings for compliance with:
    - **IS 456:2000** (Plain & Reinforced Concrete)
    - **SP 34** (Handbook on Concrete Reinforcement Detailing)
    """)
    
    st.header("📝 Instructions")
    st.markdown("""
    1. Upload your PDF or Image drawing
    2. Generate initial report
    3. Review missing information
    4. Provide additional details
    5. Generate final report
    6. Download the report
    """)
    
    if st.session_state.initial_report:
        st.success("✅ Initial report generated")
    if st.session_state.final_report:
        st.success("✅ Final report generated")

