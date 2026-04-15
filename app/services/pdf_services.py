import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.schemas.invoice_schema import InvoiceResponse

class PDFService:
    @staticmethod
    def generate_invoice_pdf(invoice: InvoiceResponse) -> bytes:
        # Resolve the absolute path to the templates directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, "../templates")
        
        # Initialize Jinja2 environment
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("invoice.html")
        
        # Render HTML with invoice data
        html_content = template.render(invoice=invoice)
        
        # Convert HTML string to PDF bytes
        pdf_bytes = HTML(string=html_content).write_pdf()
        if not pdf_bytes:
            raise RuntimeError("WeasyPrint failed to generate the PDF bytes.")
            
        return pdf_bytes