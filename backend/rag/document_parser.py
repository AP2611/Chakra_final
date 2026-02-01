"""Document parser for various file formats."""
import os
from typing import Optional
from pathlib import Path


class DocumentParser:
    """Parse documents from various file formats."""
    
    @staticmethod
    def parse_text_file(file_path: str) -> Optional[str]:
        """Parse a plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"⚠ Error parsing text file {file_path}: {e}")
            return None
    
    @staticmethod
    def parse_pdf_file(file_path: str) -> Optional[str]:
        """Parse a PDF file."""
        try:
            import PyPDF2
            text_content = []
            
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            return "\n\n".join(text_content) if text_content else None
        except ImportError:
            print("⚠ PyPDF2 not installed, PDF parsing unavailable")
            return None
        except Exception as e:
            print(f"⚠ Error parsing PDF file {file_path}: {e}")
            return None
    
    @staticmethod
    def parse_file(file_path: str) -> Optional[str]:
        """Parse a file based on its extension."""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension == '.txt':
            return DocumentParser.parse_text_file(file_path)
        elif extension == '.pdf':
            return DocumentParser.parse_pdf_file(file_path)
        else:
            print(f"⚠ Unsupported file type: {extension}")
            return None
    
    @staticmethod
    def parse_uploaded_file(file_content: bytes, filename: str) -> Optional[str]:
        """Parse an uploaded file from bytes."""
        extension = Path(filename).suffix.lower()
        
        if extension == '.txt':
            try:
                return file_content.decode('utf-8')
            except Exception as e:
                print(f"⚠ Error decoding text file: {e}")
                return None
        elif extension == '.pdf':
            try:
                import PyPDF2
                from io import BytesIO
                
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                text_content = []
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                
                return "\n\n".join(text_content) if text_content else None
            except ImportError:
                print("⚠ PyPDF2 not installed, PDF parsing unavailable")
                return None
            except Exception as e:
                print(f"⚠ Error parsing PDF: {e}")
                return None
        else:
            print(f"⚠ Unsupported file type: {extension}")
            return None

