import magic
import PyPDF2
import docxpy
import io
import re
import climage
import shutil
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter
from pygments.util import ClassNotFound
try:
    from settings import load_settings
except ImportError:
    from .settings import load_settings


def detect_file_type(data):
    file_type = magic.Magic(mime=True)
    return file_type.from_buffer(data)


def extract_text_from_pdf(data):
    pdf  = PyPDF2.PdfReader(io.BytesIO(data))
    text = ""
    for page in pdf.pages:
        text += page.extract_text()
    return re.sub(r'\s+', ' ', text.strip())


def extract_text_from_docx(data):
    return re.sub(r'\s+', ' ', docxpy.process(io.BytesIO(data)).strip())


def is_mimetype_docx(mimetype):
    return mimetype in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    )


def get_image_width():
    settings = load_settings()
    width    = settings.get("general", {}).get("cli_image_width", 0)
    if width == 0:
        return shutil.get_terminal_size().columns
    return width


def handle_code_blocks(message):
    while "```" in message:
        start = message.index("```") + 3
        # find the closing fence
        end = message.find("```", start)
        if end == -1:
            break

        block   = message[start:end].strip()
        lines   = block.split("\n")
        lang    = lines[0].strip() if lines else ""
        code    = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        try:
            lexer     = get_lexer_by_name(lang)
            formatted = highlight(code, lexer, TerminalFormatter())
        except ClassNotFound:
            formatted = f"\033[36m{block}\033[0m"

        message = message[:start - 3] + formatted + message[end + 3:]

    return message


def render_images(message):
    """replace [image_path] markers left by image_to_cli with actual unicode art"""
    width = get_image_width()

    while "[IMG:" in message and ":IMG]" in message:
        start = message.index("[IMG:") + 5
        end   = message.index(":IMG]")
        path  = message[start:end]

        try:
            img_str = "\n" + climage.convert(path, is_unicode=True, width=width)
        except Exception as e:
            img_str = f"\n[could not render image: {e}]"

        message = message[:start - 5] + img_str + message[end + 5:]

    return message


def strip_think(message):
    import re
    return re.sub(r"<think>.*?</think>", "", message, flags=re.DOTALL).strip()


def parse_message(message, show_thinking=False):
    if not message:
        return message

    if not show_thinking:
        message = strip_think(message)

    message = handle_code_blocks(message)
    message = render_images(message)

    return message
