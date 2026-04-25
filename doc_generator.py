import os
from docx import Document
from docx.shared import Inches

def generate_document(raw_dir: str) -> str:
    """
    Reads the downloaded `.txt` and `.jpg` files from the raw directory,
    combines them into a Word document, and saves the document in the same directory.
    Returns the absolute path to the created docx file.
    """
    doc = Document()
    
    # Find the text file and images
    txt_file = None
    image_files = []
    
    for filename in os.listdir(raw_dir):
        if filename.endswith(".txt"):
            txt_file = os.path.join(raw_dir, filename)
        elif filename.lower().endswith((".jpg", ".jpeg", ".png")):
            image_files.append(os.path.join(raw_dir, filename))
            
    # Sort image files to maintain order (Instaloader usually names them sequentially for carousels)
    image_files.sort()

    if txt_file and os.path.exists(txt_file):
        with open(txt_file, "r", encoding="utf-8") as f:
            caption = f.read()
        doc.add_heading("Post Content", level=1)
        doc.add_paragraph(caption)
    else:
        doc.add_heading("Post Content", level=1)
        doc.add_paragraph("(No text content found in this post)")
        
    if image_files:
        doc.add_heading("Images", level=1)
        for img_path in image_files:
            try:
                # Add image, width constrained to 6 inches to fit within margins
                doc.add_picture(img_path, width=Inches(6))
                doc.add_paragraph("") # Space after image
            except Exception as e:
                print(f"Warning: Failed to add image {img_path} to document. {e}")
                doc.add_paragraph(f"[Image could not be inserted: {os.path.basename(img_path)}]")

    # Save document
    shortcode = os.path.basename(os.path.normpath(raw_dir))
    doc_path = os.path.join(raw_dir, f"{shortcode}_combined.docx")
    doc.save(doc_path)
    
    return os.path.abspath(doc_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        res = generate_document(sys.argv[1])
        print("Document generated at:", res)
    else:
        print("Usage: python doc_generator.py <path_to_raw_dir>")
