import os
import logging
from typing import Optional, Tuple, Union, Dict, Any

from flask import (
    Flask, request, render_template, send_file, url_for, redirect, flash, abort
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from utils.ocr import extract_text_from_pdf, extract_text_from_image
from utils.summary import generate_summary
from utils.sentiment import get_sentiment
from utils.export import save_as_docx, save_as_pdf

UPLOAD_FOLDER: str = 'uploads'
RESULT_FOLDER: str = 'results'
ALLOWED_EXTENSIONS_IMAGES: set[str] = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
ALLOWED_EXTENSIONS_PDF: set[str] = {'pdf'}
MAX_FILE_SIZE_MB: int = 10
MAX_CONTENT_LENGTH_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['SECRET_KEY'] = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.errorhandler(404)
def page_not_found(e: Any) -> Tuple[str, int]:
    logger.warning(f"Page not found: {request.url} - {e}")
    flash("Sorry, the page you are looking for does not exist.", "warning")
    return render_template('index.html', error="Page not found.", MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB), 404

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e: RequestEntityTooLarge) -> Tuple[str, int]:
    logger.warning(f"File upload failed: File too large. Limit is {MAX_FILE_SIZE_MB}MB. Error: {e}")
    flash(f"The uploaded file is too large. Maximum size allowed is {MAX_FILE_SIZE_MB}MB.", "error")
    return redirect(url_for('index'))

@app.errorhandler(Exception)
def handle_generic_exception(e: Exception) -> Tuple[str, int]:
    logger.error(f"An unhandled exception occurred: {e}", exc_info=True)
    flash("An unexpected error occurred. Please try again later.", "error")
    return render_template('index.html', error="An unexpected error occurred.", MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB), 500


@app.route('/', methods=['GET', 'POST'])
def index() -> str:
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in the request. Please select a file.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected. Please select a file to upload.', 'error')
            return redirect(request.url)

        if file and file.filename:
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                file.save(path)
                logger.info(f"File '{filename}' saved to '{path}'")
            except Exception as e:
                logger.error(f"Error saving file '{filename}': {e}", exc_info=True)
                flash(f"Error saving file: {filename}. Please try again.", "error")
                return redirect(request.url)

            text_content: str = ""
            file_type_error: bool = False
            if allowed_file(filename, ALLOWED_EXTENSIONS_PDF):
                logger.info(f"Processing PDF file: {filename}")
                text_content = extract_text_from_pdf(path)
            elif allowed_file(filename, ALLOWED_EXTENSIONS_IMAGES):
                logger.info(f"Processing image file: {filename}")
                text_content = extract_text_from_image(path)
            else:
                logger.warning(f"Unsupported file type uploaded: {filename}")
                flash("Unsupported file type. Please upload a PDF or an image (PNG, JPG, GIF, BMP, TIFF).", "error")
                file_type_error = True
            
            if file_type_error:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Removed unsupported file: {path}")
                except OSError as e:
                    logger.error(f"Error removing unsupported file {path}: {e}", exc_info=True)
                return redirect(url_for('index'))

            if not text_content.strip() and not file_type_error:
                logger.warning(f"Text extraction failed or returned empty for file: {filename}")
                flash(f"Could not extract text from '{filename}'. The file might be empty, corrupted, or an image-only PDF that could not be OCR'd.", "warning")
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Removed file due to text extraction failure: {path}")
                except OSError as e:
                    logger.error(f"Error removing file {path} after text extraction failure: {e}", exc_info=True)
                return redirect(url_for('index'))

            logger.info(f"Generating summary for: {filename}")
            summary_content = generate_summary(text_content)
            logger.info(f"Analyzing sentiment for: {filename}")
            sentiment_content = get_sentiment(text_content)
            
            convert_format: Optional[str] = request.form.get('convert')
            base_filename: str = os.path.splitext(filename)[0]
            output_file_relative_path: Optional[str] = None
            
            if convert_format and convert_format != 'none':
                output_filename_base = secure_filename(base_filename)
                
                if convert_format == 'pdf':
                    output_file_name = output_filename_base + '.pdf'
                    final_file_absolute_path = os.path.join(app.config['RESULT_FOLDER'], output_file_name)
                    if save_as_pdf(final_file_absolute_path, text_content, summary_content, sentiment_content):
                        output_file_relative_path = output_file_name
                        logger.info(f"Output PDF saved: {final_file_absolute_path}")
                    else:
                        flash(f"Failed to export results as PDF for {filename}.", "error")
                elif convert_format == 'docx':
                    output_file_name = output_filename_base + '.docx'
                    final_file_absolute_path = os.path.join(app.config['RESULT_FOLDER'], output_file_name)
                    if save_as_docx(final_file_absolute_path, text_content, summary_content, sentiment_content):
                        output_file_relative_path = output_file_name
                        logger.info(f"Output DOCX saved: {final_file_absolute_path}")
                    else:
                        flash(f"Failed to export results as DOCX for {filename}.", "error")
            
            flash('File processed successfully!', 'success')
            return render_template('result.html', 
                                   text=text_content,
                                   summary=summary_content,
                                   sentiment=sentiment_content,
                                   download_path=output_file_relative_path,
                                   original_filename=filename)
        else:
            flash('An unexpected issue occurred with the file upload.', 'error')
            return redirect(request.url)

    return render_template('index.html', MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB)

@app.route('/download/<path:filename>')
def download_file(filename: str) -> Union[bytes, Tuple[str, int]]:
    logger.info(f"Download requested for file: {filename}")
    
    if ".." in filename or filename.startswith("/"):
        logger.warning(f"Potential path traversal attempt in download: {filename}")
        abort(400, "Invalid filename.")

    file_path_to_serve = os.path.join(app.config['RESULT_FOLDER'], filename)
    
    abs_result_folder = os.path.abspath(app.config['RESULT_FOLDER'])
    abs_file_path = os.path.abspath(file_path_to_serve)

    if not abs_file_path.startswith(abs_result_folder):
        logger.error(f"Path traversal attempt detected for download: {filename} resolved to {abs_file_path}")
        abort(403, "Access forbidden.")

    if os.path.isfile(file_path_to_serve):
        try:
            return send_file(file_path_to_serve, as_attachment=True)
        except Exception as e:
            logger.error(f"Error sending file {filename}: {e}", exc_info=True)
            abort(500, "Error serving file.")
    else:
        logger.warning(f"Download attempt for non-existent file: {file_path_to_serve}")
        abort(404, "File not found.")

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
