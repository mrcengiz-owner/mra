import markdown
from xhtml2pdf import pisa
import os

# Define input and output
input_file = 'API_INTEGRATION_GUIDE.md'
output_file = 'API_INTEGRATION_GUIDE.pdf'

# Read Markdown
if not os.path.exists(input_file):
    print(f"Error: {input_file} not found.")
    exit(1)

with open(input_file, 'r', encoding='utf-8') as f:
    text = f.read()

# Convert Markdown to HTML
# Enable 'tables' and 'fenced_code' for code blocks
html_body = markdown.markdown(text, extensions=['tables', 'fenced_code'])

# Wrap in HTML structure with CSS for Styling (and Turkish character support)
html_substance = f"""
<html>
<head>
<meta charset="utf-8">
</head>
<body>
    {html_body}
</body>
</html>
"""

# Convert to PDF
with open(output_file, "wb") as pdf_file:
    pisa_status = pisa.CreatePDF(
        html_substance, 
        dest=pdf_file,
        encoding='utf-8'
    )

if pisa_status.err:
    print(f"Error creating PDF: {pisa_status.err}")
else:
    print(f"Success! PDF created at: {os.path.abspath(output_file)}")
