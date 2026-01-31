# Website Index Files

## Quick Answer

The **primary website index file** for this repository is:
```
templates/index.html
```

This file is served by the main Flask application (`app.py`) at the root route `/` when you run:
```bash
python app.py
```

## Complete Overview

This repository contains **two separate Flask web applications**, each with its own index file:

### 1. Main Application (Primary)
- **Entry Point**: `app.py`
- **Index File**: `templates/index.html`
- **Port**: 5000 (default)
- **URL**: http://localhost:5000/
- **Purpose**: Natural language to SQL query conversion for Premier League soccer data
- **Features**:
  - Natural language question input
  - SQL query generation via Gemini AI
  - Database query execution
  - Dynamic visualization generation
  - Database update functionality

### 2. Visualization Gallery (Secondary)
- **Entry Point**: `viz-static-site/app.py`
- **Index File**: `viz-static-site/templates/index.html`
- **Port**: 5005
- **URL**: http://localhost:5005/
- **Purpose**: Pre-defined visualizations gallery for Premier League data
- **Features**:
  - Browse 8+ pre-defined visualizations
  - Interactive plot selection
  - Player and team statistics charts

## How to Access

### Main Application
```bash
# From repository root
python app.py
# Then visit: http://localhost:5000
```

### Visualization Gallery
```bash
# From repository root
cd viz-static-site
python app.py
# Then visit: http://localhost:5005
```

## File Paths (Absolute)

For reference, the absolute file paths are:
- Main index: `/home/runner/work/SportSQL/SportSQL/templates/index.html`
- Visualization gallery index: `/home/runner/work/SportSQL/SportSQL/viz-static-site/templates/index.html`
