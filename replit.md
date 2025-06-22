# replit.md

## Overview

This is a LinkedIn Job Scraper application built with Flask that extracts job listings from LinkedIn URLs and provides AI-powered job analysis. The system scrapes job details, stores them in a database, and optionally analyzes job compatibility using Google's Gemini AI.

## System Architecture

The application follows a modular Flask architecture with the following components:

- **Frontend**: Bootstrap-based web interface with dark theme
- **Backend**: Flask web server with SQLAlchemy ORM
- **Database**: PostgreSQL database for persistent storage
- **AI Integration**: Google Gemini API for job analysis
- **Web Scraping**: Custom LinkedIn scraper with proxy rotation
- **Deployment**: Gunicorn WSGI server on Replit

## Key Components

### Web Application (`main.py`)
- Flask application with session management
- Real-time progress tracking for batch processing
- RESTful API endpoints for scraping and analysis
- Database initialization and management

### LinkedIn Scraper (`linkedin_scraper.py`)
- Web scraping engine with proxy rotation support
- HTML parsing using BeautifulSoup and trafilatura
- Batch processing with configurable sizes
- Export functionality to CSV/Excel formats

### AI Job Analyzer (`gemini_analyzer.py`)
- Google Gemini API integration for job analysis
- Structured JSON response schema for compatibility scoring
- Portuguese language support for analysis results
- Retry logic and error handling

### Database Models (`models.py`)
- `ProcessedBatch`: Stores processed job batches with results
- `IgnoredURL`: Maintains list of URLs to skip during processing
- SQLAlchemy ORM with PostgreSQL backend

### Frontend Components
- Responsive Bootstrap UI with dark theme
- Real-time progress updates via JavaScript
- Modal dialogs for batch selection and analysis details
- Export functionality for processed results

## Data Flow

1. **Input**: User submits LinkedIn job URLs through web interface
2. **Processing**: URLs are batched and processed sequentially
3. **Scraping**: Each URL is scraped for job details and company information
4. **Storage**: Results are stored in PostgreSQL database
5. **Analysis** (Optional): Job descriptions are analyzed using Gemini AI
6. **Output**: Results displayed in web interface and exportable to CSV/Excel

## External Dependencies

### Core Dependencies
- Flask 3.1.0 - Web framework
- SQLAlchemy 3.1.1 - Database ORM
- PostgreSQL - Primary database
- Gunicorn 23.0.0 - WSGI server

### Scraping Dependencies
- BeautifulSoup4 4.13.3 - HTML parsing
- requests-html 0.10.0 - Web requests with JavaScript support
- trafilatura 2.0.0 - Content extraction
- selenium 4.30.0 - Browser automation
- lxml 5.3.1 - XML/HTML processing

### AI Dependencies
- google-genai 1.9.0 - Google Gemini API client
- google-ai-generativelanguage 0.6.15 - Additional Gemini support

### Data Processing Dependencies
- pandas 2.2.3 - Data manipulation
- openpyxl 3.1.5 - Excel file handling

## Deployment Strategy

The application is configured for deployment on Replit with:

- **Runtime**: Python 3.11 with Nix package management
- **Web Server**: Gunicorn with auto-scaling deployment target
- **Database**: PostgreSQL with connection pooling
- **Environment**: Containerized environment with required system packages
- **Process Management**: Workflow-based startup with automatic restarts

### Environment Variables Required
- `GEMINI_API_KEY` - Google Gemini API key for job analysis
- `DATABASE_URL` - PostgreSQL connection string
- `SESSION_SECRET` - Flask session secret key

### System Packages
- geckodriver - Selenium WebDriver for Firefox
- postgresql - Database server
- openssl - Cryptographic library
- zlib - Compression library

## Changelog

- June 22, 2025. Removed unwanted data fields per user request
  - Removed collection and export of company_link field from LinkedIn scraper
  - Removed collection and export of searched_at timestamp field
  - Removed idioma_descricao and tipo_vaga fields from Gemini AI analysis
  - Updated HTML templates and export functions to exclude removed fields
  - Simplified data structure by focusing on essential job information only
- June 22, 2025. Fixed critical pandas dependency issues and export functionality
  - Resolved numpy/pandas import failures that prevented application startup
  - Simplified code by removing unnecessary fallback logic for pandas
  - Fixed CSV/Excel export functionality that was failing due to data access issues
  - Corrected batch data retrieval to use database instead of memory structures
  - All export features now working correctly with Gemini AI analysis
- June 19, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.