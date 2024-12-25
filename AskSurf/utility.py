import magic
import PyPDF2
import docxpy
import io
import climage
import re


def detect_file_type(data):
    """Detect the file type of the data"""
    file_type = magic.Magic(mime=True)
    return file_type.from_buffer(data)


def extract_text_from_pdf(data):
    """Extract text from a PDF file"""
    pdf = PyPDF2.PdfReader(io.BytesIO(data))
    text = ""
    for page in pdf.pages:
        text += page.extract_text()
    return re.sub(r'\s+', ' ', text.strip())


def extract_text_from_docx(data):
    """Extract text from a DOCX file"""
    return re.sub(r'\s+', ' ', docxpy.process(io.BytesIO(data)).strip())


def is_mimetype_docx(mimetype):
    """Check if the mimetype is a DOCX file"""
    return mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or mimetype == "application/msword"


def handle_code_blocks(message):
    code_block_start = "```"
    code_block_end = "```"
    while code_block_start in message and code_block_end in message:
        start_index = message.index(code_block_start) + len(code_block_start)
        end_index = message.index(code_block_end, start_index)
        code_block_content = message[start_index:end_index].strip()
        # Extract the language or name from the first line
        lines = code_block_content.split("\n")
        if lines:
            code_name = lines[0].strip()
            code_body = "\n".join(lines[1:]).strip()
            # Format the code block
            formatted_code_block = (
                f"--- {code_name} ---\n"
                f"\033[36m{code_body}\033[0m\n"  # Cyan color for code
                "--- end ---"
            )
            message = message[:start_index - len(code_block_start)] + formatted_code_block + message[end_index + len(code_block_end):]
    return message


def parse_message(message):
    # remove the first and last characters
    message = message[2:-1]

    # replace the tags with the correct color codes
    message = message.replace("[R]", "\033[31m")
    message = message.replace("[Y]", "\033[33m")
    message = message.replace("[O]", "\033[33m")
    message = message.replace("[G]", "\033[32m")
    message = message.replace("[P]", "\033[35m")
    message = message.replace("[B]", "\033[34m")
    message = message.replace("[N]", "\033[0m")

    # replace all end tags with the normal color code
    message = message.replace("[/R]", "\033[0m")
    message = message.replace("[/Y]", "\033[0m")
    message = message.replace("[/O]", "\033[0m")
    message = message.replace("[/G]", "\033[0m")
    message = message.replace("[/P]", "\033[0m")
    message = message.replace("[/B]", "\033[0m")
    message = message.replace("[/N]", "\033[0m")

    message = message.replace('\\"', '"')
    message = message.replace('\"', '"')
    message = message.replace("/n", "\n")
    message = message.replace("\\n", "\n")

    # Make image tags all caps if they are not
    message = message.replace("[i]", "[I]")
    message = message.replace("[/i]", "[/I]")

    while "[I]" in message and "[/I]" in message:
        start_index = message.index("[I]") + len("[I]")
        end_index = message.index("[/I]")
        image_path = message[start_index:end_index]
        image_str = "\n" + climage.convert(image_path, is_unicode=True, width=100)
        message = message[:start_index - len("[I]")] + image_str + message[end_index + len("[/I]"):]

    message = handle_code_blocks(message)

    return message
