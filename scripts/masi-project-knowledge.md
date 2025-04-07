# Masi Web Project Knowledge Base

## Project Overview

This is a Django web application for the Masinyusane organization, consisting of multiple Django apps, templates, static assets, and utility scripts.

## Django Apps

### core
**Purpose:** Core application providing base functionality and shared utilities
**Path:** `/core`

**Key Components:**
- `__init__.py`: Python package initialization
- `admin.py`: Django admin configuration
- `apps.py`: Django app configuration
- `context_processors.py`: Template context processors
- `models.py`: Database models
- `tests.py`: Unit tests
- `views.py`: View functions/classes

**Utilities:**
- `utils/helpers.py`: Helper functions for the core app

### dashboards
**Purpose:** Dashboard application for data visualization and analysis
**Path:** `/dashboards`

**Key Components:**
- `__init__.py`: Python package initialization
- `admin.py`: Django admin configuration
- `apps.py`: Django app configuration
- `forms.py`: Form definitions
- `models.py`: Database models
- `tests.py`: Unit tests
- `urls.py`: URL routing
- `views.py`: View functions/classes

**Sub-modules:**
- `services/`: Service layer components
  - `airtable_service.py`: Integration with Airtable
  - `data_processing.py`: Data processing logic
- `visualizations/`: Chart and visualization components
  - `charts.py`: General chart creation
  - `mentor_charts.py`: Mentor-specific visualizations
- `utils/text_utils.py`: Text processing utilities
- `management/commands/`: Custom management commands

### pages
**Purpose:** Public-facing website pages and content
**Path:** `/pages`

**Key Components:**
- `__init__.py`: Python package initialization
- `admin.py`: Django admin configuration
- `apps.py`: Django app configuration
- `models.py`: Database models
- `tests.py`: Unit tests
- `urls.py`: URL routing
- `views.py`: View functions/classes

### masi_website
**Purpose:** Main project configuration and settings
**Path:** `/masi_website`

**Key Components:**
- `__init__.py`: Python package initialization
- `asgi.py`: ASGI application entry point
- `settings.py`: Django settings
- `urls.py`: Root URL configuration
- `wsgi.py`: WSGI application entry point

## Template Structure

The project uses a hierarchical template structure with a base template (`base.html`) that other templates extend.

### Main Template Groups:
- `account/`: Authentication templates
- `dashboards/`: Dashboard view templates
- `pages/`: Public website page templates
- `partials/`: Reusable template components (navbar, footer)
- `registration/`: User registration and password reset templates

### Key Templates:
- `base.html`: Base template with common structure
- `pages/home.html`: Homepage template
- `pages/about.html`: About page
- `pages/donate.html`: Donation page
- `dashboards/dashboard_main.html`: Main dashboard view
- `dashboards/mentor_dashboard.html`: Mentor-specific dashboard
- `partials/navbar.html`: Navigation bar component
- `partials/footer.html`: Footer component

## Static Assets

### CSS
- `main.css`: Main stylesheet
- `styles.css`: Additional styles

### JavaScript
- `bootstrap.bundle.min.js`: Bootstrap framework
- `lightbox-plus-jquery.min.js`: Lightbox for images with jQuery
- `plotly-chart.js`: Plotly.js for data visualization
- `script.js`, `script2.js`, `script3.js`: Custom scripts

### Data
- `schools_list_mar14.csv`: School data

### Media
The project includes numerous image and video assets for the website content, including:
- Logos and branding
- Staff and graduate photos
- Report covers
- Banners and background images
- Video content

### SCSS
The project uses SCSS for CSS preprocessing with organized directories:
- `abstracts/`: Variables, mixins, etc.
- `components/`: Reusable component styles
- `layouts/`: Layout styles
- `pages/`: Page-specific styles
- `main.scss`: Main SCSS entry point

## Deployment and Build

- `build.sh`: Build script for deployment
- `requirements.txt`: Python dependencies
- `moonlit-botany-454016-b5-e20993bb54e0.json`: Google Cloud service account credentials

## Database
- Database info saved in the .env. We're using Postgres and serving on Render.
- Database migrations in each app's `migrations/` directory

## Utility Scripts
- `manage.py`: Django management script
- `delete-fake-data.py`: Script to remove test data
- `generate-fake-data.py`: Script to create test data
- `export_code.py` and `export_code_short.py`: Code export utilities

## Project Organization Insights

1. **Django MVT Architecture**: The project follows Django's Model-View-Template architecture with clear separation of concerns.

2. **Multiple Apps**: The project is divided into focused apps with specific responsibilities:
   - `core`: Shared functionality
   - `dashboards`: Data visualization and analysis
   - `pages`: Public-facing content
   - `masi_website`: Configuration and settings

3. **Frontend Technologies**:
   - Bootstrap for responsive design
   - SCSS for CSS preprocessing
   - Plotly.js for data visualization
   - jQuery for DOM manipulation

4. **Deployment Strategy**:
   - Google Cloud Platform integration
   - Custom build script
   - Standard Django deployment practices with staticfiles

5. **Development Patterns**:
   - Service layer in dashboards app
   - Custom management commands
   - Data visualization components
   - Reusable template partials

## File Type Analysis

- **Python (.py)**: 49 files - Core application logic
- **HTML (.html)**: 21 files - Templates and views
- **JavaScript (.js)**: 13 files - Frontend interactivity
- **CSS/SCSS**: 6 files - Styling (4 CSS, 2 SCSS)
- **Media Files**:
  - Images: 180 files (80 PNG, 74 JPG, 24 WEBP, 2 SVG)
  - Video: 24 MP4 files
  - Documents: 34 PDF files
- **Configuration**:
  - 3 JSON files
  - 5 TXT files (including requirements.txt)
  - 1 Shell script (build.sh)
- **Fonts**: 16 files (8 TTF, 8 WOFF2)
- **Data**: 2 CSV files

## Additional Technology Insights

1. **Content-Rich Application**: The high number of media files (204) indicates this is a content-rich application with substantial visual elements.

2. **Documentation Focus**: With 34 PDF files in the reports directory, the project appears to maintain significant documentation or publications.

3. **Modern Frontend**: The combination of SCSS preprocessing, multiple JavaScript files, and webfonts suggests a modern frontend approach.

4. **Small Data Footprint**: Only 2 CSV files indicate that most data may be stored in the database rather than static files.

5. **Testing Presence**: The project includes test files, indicating some level of automated testing infrastructure.
