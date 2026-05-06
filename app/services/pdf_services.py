import os

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.i18n import DEFAULT_LANGUAGE, translate
from app.core.message_keys import Msg
from app.schemas.invoice_schema import InvoiceResponse


class PDFService:
    @staticmethod
    def _invoice_pdf_labels(language: str | None) -> dict[str, str]:
        return {
            "tax_invoice": translate(Msg.INVOICE_PDF_TAX_INVOICE, language),
            "invoice_no": translate(Msg.INVOICE_PDF_INVOICE_NO, language),
            "date": translate(Msg.INVOICE_PDF_DATE, language),
            "transaction_id": translate(Msg.INVOICE_PDF_TRANSACTION_ID, language),
            "not_available": translate(Msg.INVOICE_PDF_NOT_AVAILABLE, language),
            "billed_to": translate(Msg.INVOICE_PDF_BILLED_TO, language),
            "shipped_to": translate(Msg.INVOICE_PDF_SHIPPED_TO, language),
            "item": translate(Msg.INVOICE_PDF_ITEM, language),
            "sku": translate(Msg.INVOICE_PDF_SKU, language),
            "qty": translate(Msg.INVOICE_PDF_QTY, language),
            "unit_price": translate(Msg.INVOICE_PDF_UNIT_PRICE, language),
            "total": translate(Msg.INVOICE_PDF_TOTAL, language),
            "subtotal": translate(Msg.INVOICE_PDF_SUBTOTAL, language),
            "tax": translate(Msg.INVOICE_PDF_TAX, language),
            "shipping": translate(Msg.INVOICE_PDF_SHIPPING, language),
            "grand_total": translate(Msg.INVOICE_PDF_GRAND_TOTAL, language),
        }

    @staticmethod
    def generate_invoice_pdf(invoice: InvoiceResponse, language: str | None = None) -> bytes:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, "../templates")

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("invoice.html")

        resolved_language = language or DEFAULT_LANGUAGE
        html_content = template.render(
            invoice=invoice,
            labels=PDFService._invoice_pdf_labels(resolved_language),
            language=resolved_language,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()
        if not pdf_bytes:
            raise RuntimeError("WeasyPrint failed to generate the PDF bytes.")

        return pdf_bytes