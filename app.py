import os
import re
import shutil
import socket
import time
import uuid
import zipfile
import ipaddress
from urllib.parse import urljoin, urlparse
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file
from bs4 import BeautifulSoup
import requests

app = Flask(__name__)

CLONED_SITES_DIR = "cloned_sites"
MAX_PAGES = 50
MAX_ASSETS = 200
REQUEST_TIMEOUT = 10
RATE_LIMIT_DELAY = 0.5

os.makedirs(CLONED_SITES_DIR, exist_ok=True)

BLOCKED_DOMAINS = [
    'facebook.com', 'google.com', 'twitter.com', 'instagram.com',
    'linkedin.com', 'amazon.com', 'paypal.com', 'bank', 'gov',
    'metadata.google.internal', '169.254.169.254'
]

PRIVATE_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('100.64.0.0/10'),
    ipaddress.ip_network('198.18.0.0/15'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]

def is_private_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in PRIVATE_IP_RANGES:
            if ip in network:
                return True
        return False
    except ValueError:
        return True

def resolve_and_check_url(url):
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.split(':')[0]
        
        if hostname.replace('.', '').isdigit() or ':' in hostname:
            if is_private_ip(hostname):
                return False, "Cannot access private/internal IP addresses"
        
        try:
            ip_addresses = socket.getaddrinfo(hostname, None)
            for addr_info in ip_addresses:
                ip = addr_info[4][0]
                if is_private_ip(ip):
                    return False, "Cannot access private/internal IP addresses"
        except socket.gaierror:
            return False, "Could not resolve hostname"
        
        return True, None
    except Exception as e:
        return False, str(e)

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ['http', 'https'] and bool(parsed.netloc)
    except:
        return False

def is_blocked_domain(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return True
    return False

def sanitize_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if not path:
        return 'index.html'
    path = re.sub(r'[^\w\-_./]', '_', path)
    if not path.endswith(('.html', '.htm', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.woff', '.woff2', '.ttf', '.eot')):
        path = path.rstrip('/') + '/index.html'
    return path

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

class WebsiteCloner:
    def __init__(self, url, clone_id):
        self.base_url = url
        self.clone_id = clone_id
        self.base_domain = urlparse(url).netloc
        self.output_dir = os.path.join(CLONED_SITES_DIR, clone_id)
        self.downloaded_urls = set()
        self.assets_downloaded = 0
        self.pages_downloaded = 0
        self.errors = []
        self.session = requests.Session()
        self.session.headers.update(get_headers())
    
    def clone(self):
        os.makedirs(self.output_dir, exist_ok=True)
        
        try:
            self.download_page(self.base_url)
            return {
                'success': True,
                'clone_id': self.clone_id,
                'pages_downloaded': self.pages_downloaded,
                'assets_downloaded': self.assets_downloaded,
                'errors': self.errors[:10]
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'clone_id': self.clone_id
            }
    
    def download_page(self, url, depth=0):
        if depth > 2 or self.pages_downloaded >= MAX_PAGES:
            return
        
        if url in self.downloaded_urls:
            return
        
        self.downloaded_urls.add(url)
        
        try:
            time.sleep(RATE_LIMIT_DELAY)
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type:
                return
            
            self.pages_downloaded += 1
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            self.download_css(soup, url)
            self.download_scripts(soup, url)
            self.download_images(soup, url)
            self.download_fonts(soup, url)
            
            self.rewrite_links(soup, url)
            
            filename = sanitize_filename(url)
            filepath = os.path.join(self.output_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            if depth < 1:
                for link in soup.find_all('a', href=True):
                    href = str(link['href'])
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)
                    
                    if parsed.netloc == self.base_domain and parsed.scheme in ['http', 'https']:
                        self.download_page(full_url, depth + 1)
        
        except Exception as e:
            self.errors.append(f"Error downloading {url}: {str(e)}")
    
    def download_asset(self, url, asset_type='asset'):
        if url in self.downloaded_urls or self.assets_downloaded >= MAX_ASSETS:
            return None
        
        self.downloaded_urls.add(url)
        
        try:
            time.sleep(RATE_LIMIT_DELAY / 2)
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            self.assets_downloaded += 1
            
            filename = sanitize_filename(url)
            filepath = os.path.join(self.output_dir, 'assets', asset_type, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return os.path.relpath(filepath, self.output_dir)
        
        except Exception as e:
            self.errors.append(f"Error downloading asset {url}: {str(e)}")
            return None
    
    def download_css(self, soup, page_url):
        for link in soup.find_all('link', rel='stylesheet'):
            if link.get('href'):
                css_url = urljoin(page_url, link['href'])
                local_path = self.download_asset(css_url, 'css')
                if local_path:
                    link['href'] = local_path
    
    def download_scripts(self, soup, page_url):
        for script in soup.find_all('script', src=True):
            js_url = urljoin(page_url, script['src'])
            local_path = self.download_asset(js_url, 'js')
            if local_path:
                script['src'] = local_path
    
    def download_images(self, soup, page_url):
        for img in soup.find_all('img', src=True):
            img_url = urljoin(page_url, img['src'])
            local_path = self.download_asset(img_url, 'images')
            if local_path:
                img['src'] = local_path
        
        for elem in soup.find_all(style=True):
            style = elem['style']
            urls = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style)
            for url in urls:
                if url.startswith('data:'):
                    continue
                full_url = urljoin(page_url, url)
                local_path = self.download_asset(full_url, 'images')
                if local_path:
                    style = style.replace(url, local_path)
                    elem['style'] = style
    
    def download_fonts(self, soup, page_url):
        for link in soup.find_all('link', rel='preload'):
            if link.get('as') == 'font' and link.get('href'):
                font_url = urljoin(page_url, link['href'])
                local_path = self.download_asset(font_url, 'fonts')
                if local_path:
                    link['href'] = local_path
    
    def rewrite_links(self, soup, page_url):
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                continue
            
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)
            
            if parsed.netloc == self.base_domain:
                local_path = sanitize_filename(full_url)
                link['href'] = local_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/clone', methods=['POST'])
def clone_website():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'Please provide a URL'}), 400
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    if not is_valid_url(url):
        return jsonify({'success': False, 'error': 'Invalid URL format'}), 400
    
    if is_blocked_domain(url):
        return jsonify({'success': False, 'error': 'This domain cannot be cloned for security reasons'}), 403
    
    is_safe, error_msg = resolve_and_check_url(url)
    if not is_safe:
        return jsonify({'success': False, 'error': error_msg}), 403
    
    clone_id = str(uuid.uuid4())[:8]
    
    cloner = WebsiteCloner(url, clone_id)
    result = cloner.clone()
    
    return jsonify(result)

@app.route('/download/<clone_id>')
def download_clone(clone_id):
    clone_dir = os.path.join(CLONED_SITES_DIR, clone_id)
    
    if not os.path.exists(clone_dir):
        return jsonify({'success': False, 'error': 'Clone not found'}), 404
    
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(clone_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, clone_dir)
                zf.write(file_path, arc_name)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'cloned_site_{clone_id}.zip'
    )

@app.route('/preview/<clone_id>')
def preview_clone(clone_id):
    clone_dir = os.path.join(CLONED_SITES_DIR, clone_id)
    index_path = os.path.join(clone_dir, 'index.html')
    
    if not os.path.exists(index_path):
        return "Clone not found or index.html missing", 404
    
    with open(index_path, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/list')
def list_clones():
    if not os.path.exists(CLONED_SITES_DIR):
        return jsonify({'clones': []})
    
    clones = []
    for clone_id in os.listdir(CLONED_SITES_DIR):
        clone_path = os.path.join(CLONED_SITES_DIR, clone_id)
        if os.path.isdir(clone_path):
            clones.append({
                'id': clone_id,
                'created': os.path.getctime(clone_path)
            })
    
    clones.sort(key=lambda x: x['created'], reverse=True)
    return jsonify({'clones': clones})

@app.route('/delete/<clone_id>', methods=['DELETE'])
def delete_clone(clone_id):
    clone_dir = os.path.join(CLONED_SITES_DIR, clone_id)
    
    if not os.path.exists(clone_dir):
        return jsonify({'success': False, 'error': 'Clone not found'}), 404
    
    try:
        shutil.rmtree(clone_dir)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
