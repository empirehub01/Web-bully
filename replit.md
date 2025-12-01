# Website Cloner - Development Tool

## Overview
A secure web-based tool for cloning websites for development and testing purposes. This application allows you to download HTML, CSS, JavaScript, images, and other assets from websites for offline analysis and reference.

## Features
- Clone websites including HTML pages, CSS stylesheets, JavaScript files, and images
- Automatic link rewriting for local browsing
- Rate limiting to respect target servers
- Security measures to prevent misuse (SSRF protection, blocked domains)
- Download cloned sites as ZIP archives
- Preview cloned sites directly in browser
- History of recent clones

## Security Measures
- SSRF (Server-Side Request Forgery) protection - blocks access to private/internal IP ranges
- Blocked domain list for major platforms (social media, banking, government sites)
- Cloud metadata endpoint protection
- Rate limiting to prevent server abuse

## Technical Details
- **Backend**: Python Flask
- **Frontend**: HTML/CSS/JavaScript (vanilla)
- **Port**: 5000

## Usage
1. Enter a website URL in the input field
2. Click "Clone Website" to start the cloning process
3. Once complete, download the ZIP file or preview the clone
4. Manage previous clones from the history section

## Limitations
- Maximum 50 pages per clone
- Maximum 200 assets per clone
- Depth limit of 2 levels for internal links
- Some websites may block cloning attempts

## Recent Changes
- December 1, 2025: Initial implementation with SSRF protection

## Project Structure
```
/
├── app.py              # Flask backend with cloning logic
├── templates/
│   └── index.html      # Web interface
├── cloned_sites/       # Directory for cloned website files
└── replit.md           # This documentation file
```
