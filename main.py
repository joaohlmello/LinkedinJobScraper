from flask import Flask, render_template, request, flash
import os
import logging
from linkedin_scraper import get_results_html

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Home route for the LinkedIn Job Scraper app.
    Handles both GET and POST requests.
    """
    results_html = None
    
    if request.method == 'POST':
        # Get LinkedIn URLs from the form
        linkedin_urls_text = request.form.get('linkedin_urls', '')
        linkedin_urls = [url.strip() for url in linkedin_urls_text.split('\n') if url.strip()]
        
        if not linkedin_urls:
            flash('Please enter at least one LinkedIn job URL.', 'danger')
        else:
            # Process the URLs and get results
            try:
                results_html = get_results_html(linkedin_urls)
                if "Error" in results_html:
                    flash('There was an error processing one or more URLs. Check the results below.', 'warning')
                else:
                    flash('LinkedIn job information extracted successfully!', 'success')
            except Exception as e:
                logger.error(f"Error processing URLs: {str(e)}")
                flash(f'An error occurred: {str(e)}', 'danger')
    
    return render_template('index.html', results_html=results_html)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('index.html', error="Server error occurred"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
