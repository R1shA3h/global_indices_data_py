from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import os
import logging
from datetime import datetime
import pymongo
from urllib.parse import quote_plus

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_selenium():
    """
    Set up and return a Selenium WebDriver.
    Returns None if selenium is not installed or if there are driver issues.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Create a new Chrome webdriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        return driver, WebDriverWait, By, EC
    except ImportError as e:
        logger.warning(f"Selenium imports failed: {e}. Falling back to requests-only mode.")
        logger.warning("To use Selenium, install: pip install selenium webdriver-manager")
        return None, None, None, None
    except Exception as e:
        logger.error(f"Error setting up Selenium: {e}")
        return None, None, None, None

def connect_to_mongodb(connection_string, db_name, collection_name):
    """
    Connect to MongoDB and return the collection.
    
    Args:
        connection_string (str): MongoDB connection string
        db_name (str): Database name
        collection_name (str): Collection name
        
    Returns:
        tuple: (client, collection) - MongoDB client and collection
    """
    try:
        # Connect to MongoDB
        client = pymongo.MongoClient(connection_string)
        
        # Test connection
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        logger.info(f"Using MongoDB collection: {db_name}.{collection_name}")
        
        return client, collection
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None, None

def store_data_in_mongodb(data, collection, use_limit=True, limit=100):
    """
    Store data in MongoDB, optionally limiting the number of records.
    
    Args:
        data (list): List of dictionaries containing indices data
        collection (pymongo.collection.Collection): MongoDB collection
        use_limit (bool): Whether to limit the number of records
        limit (int): Maximum number of records to keep
        
    Returns:
        bool: True if successful, False otherwise
    """
    if collection is None:
        logger.error("MongoDB collection is None")
        return False
        
    try:
        # Remove change_percent field from each record
        for record in data:
            if 'change_percent' in record:
                del record['change_percent']
        
        # Add timestamp for all records
        timestamp = datetime.now()
        for record in data:
            record['timestamp'] = timestamp
        
        # Clear existing data if we're using a limit
        if use_limit:
            collection.delete_many({})
            logger.info("Cleared existing data from MongoDB collection")
            
            # Insert only the data we need (limited to most recent entries)
            if data:
                # Limit data to the specified number of records
                data_to_insert = data[:limit]
                result = collection.insert_many(data_to_insert)
                logger.info(f"Inserted {len(result.inserted_ids)} records into MongoDB (limited to {limit})")
                return True
        else:
            # Just insert all the data
            result = collection.insert_many(data)
            logger.info(f"Inserted {len(result.inserted_ids)} records into MongoDB")
            return True
            
        if not data:
            logger.warning("No data to insert into MongoDB")
            return False
    except Exception as e:
        logger.error(f"Failed to store data in MongoDB: {e}")
        return False

def fetch_with_requests():
    """Fetch page content using requests."""
    url = "https://groww.in/indices/global-indices"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://groww.in/",
        "Origin": "https://groww.in"
    }
    
    try:
        logger.info("Fetching the webpage with requests...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error during request: {e}")
        return None

def fetch_with_selenium():
    """Fetch page content using Selenium."""
    driver, WebDriverWait, By, EC = setup_selenium()
    if not driver:
        return None
    
    url = "https://groww.in/indices/global-indices"
    try:
        logger.info("Fetching with Selenium...")
        driver.get(url)
        
        # Wait for the page to load (adjust timeout as needed)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(5)
        
        # Try to find the table or relevant container
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
            )
        except:
            # Table might not be present, just continue
            pass
        
        # Get the page source after JavaScript execution
        page_source = driver.page_source
        logger.info("Successfully fetched page with Selenium")
        return page_source
    except Exception as e:
        logger.error(f"Error with Selenium: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Selenium driver closed")
            except:
                pass

def extract_from_script_tags(soup):
    """Extract data from script tags in the HTML."""
    logger.info("Looking for data in script tags...")
    scripts = soup.find_all('script')
    data = None
    
    for script in scripts:
        if script.string and 'window.__INITIAL_STATE__' in script.string:
            logger.info("Found data in script tag")
            try:
                # Extract JSON data
                json_str = script.string.split('window.__INITIAL_STATE__ = ')[1].split('};')[0] + '}'
                data = json.loads(json_str)
                break
            except Exception as e:
                logger.error(f"Error parsing script tag JSON: {e}")
    
    return data

def fetch_from_api():
    """Try to fetch data directly from the API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://groww.in/",
        "Origin": "https://groww.in",
        "Content-Type": "application/json"
    }
    
    try:
        api_url = "https://groww.in/v1/api/stocks_data/global_indices"
        
        api_response = requests.get(api_url, headers=headers)
        api_response.raise_for_status()
        
        return api_response.json()
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return None

def process_json_data(data):
    """Process JSON data to extract indices information."""
    indices_data = []
    
    logger.info(f"Data structure: {type(data)}")
    if isinstance(data, dict):
        logger.info(f"Top-level keys: {list(data.keys())}")
        
        # Try various possible data structures
        indices_list = None
        
        # Dynamically try to find indices data in the response
        if 'indices' in data:
            logger.info("Found indices in top level")
            indices_list = data['indices']
        elif 'data' in data and 'indices' in data['data']:
            logger.info("Found indices in data.indices")
            indices_list = data['data']['indices']
        elif 'data' in data and isinstance(data['data'], list):
            logger.info("Found data array")
            indices_list = data['data']
        else:
            # Search recursively for arrays that might contain indices
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    # Check if items look like they could be indices
                    if isinstance(value[0], dict) and ('name' in value[0] or 'index' in value[0]):
                        indices_list = value
                        logger.info(f"Found potential indices list in {key}")
                        break
        
        # Process the indices list
        if indices_list and isinstance(indices_list, list):
            for index in indices_list:
                if isinstance(index, dict):
                    index_data = {
                        'name': index.get('name', ''),
                        'change': index.get('change', index.get('absoluteChange', '')),
                        # Add new fields
                        'high': index.get('high', index.get('dayHigh', '')),
                        'low': index.get('low', index.get('dayLow', '')),
                        'open': index.get('open', index.get('openPrice', '')),
                        'prev_close': index.get('prevClose', index.get('previousClose', '')),
                        # 'change_percent' field removed as requested
                        'timestamp': index.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    }
                    indices_data.append(index_data)
    
    return indices_data

def extract_from_html(soup):
    """Extract indices data directly from HTML as a fallback method."""
    indices_data = []
    
    # Look for tables
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        if len(rows) <= 1:  # Skip tables with just headers or empty
            continue
        
        # Check if this looks like an indices table
        header_cells = rows[0].find_all(['th', 'td'])
        header_texts = [cell.text.strip().lower() for cell in header_cells]
        
        # If we find headers that look like indices table, process it
        if any(kw in ' '.join(header_texts) for kw in ['index', 'price', 'change']):
            # Map header position to field name
            header_map = {}
            for i, header in enumerate(header_texts):
                if 'index' in header or 'name' in header:
                    header_map['name'] = i
                elif 'price' in header or 'value' in header or 'ltp' in header:
                    header_map['price'] = i  # Keep mapping but don't use in result
                elif 'change' in header and 'percent' not in header:
                    header_map['change'] = i
                elif 'high' in header or 'day high' in header:
                    header_map['high'] = i
                elif 'low' in header or 'day low' in header:
                    header_map['low'] = i
                elif 'open' in header or 'opening' in header:
                    header_map['open'] = i
                elif 'prev' in header or 'previous' in header or 'close' in header:
                    header_map['prev_close'] = i
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_all('td')
                if len(cells) >= 3:  # Ensure we have enough cells
                    # Try to extract data
                    name_cell = cells[header_map.get('name', 0)]
                    
                    # Extract the name (might be in a child element)
                    name_element = name_cell.find('div') or name_cell
                    name = name_element.text.strip()
                    
                    # Create data record
                    index_data = {
                        'name': name,
                        'change': cells[header_map.get('change', 2)].text.strip() if 'change' in header_map and header_map['change'] < len(cells) else '',
                        'high': cells[header_map.get('high', 0)].text.strip() if 'high' in header_map and header_map['high'] < len(cells) else '',
                        'low': cells[header_map.get('low', 0)].text.strip() if 'low' in header_map and header_map['low'] < len(cells) else '',
                        'open': cells[header_map.get('open', 0)].text.strip() if 'open' in header_map and header_map['open'] < len(cells) else '',
                        'prev_close': cells[header_map.get('prev_close', 0)].text.strip() if 'prev_close' in header_map and header_map['prev_close'] < len(cells) else '',
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    indices_data.append(index_data)
    
    # If no tables were found or processed, try looking for div-based structures
    if not indices_data:
        # Look for common patterns in financial websites
        index_rows = soup.select('div.index-row, div.table-row, div.list-item')
        for row in index_rows:
            name_elem = row.select_one('.name, .index-name, .title')
            price_elem = row.select_one('.price, .value, .ltp')  # Still select but don't use
            change_elem = row.select_one('.change, .absolute-change')
            high_elem = row.select_one('.high, .day-high')
            low_elem = row.select_one('.low, .day-low')
            open_elem = row.select_one('.open, .open-price')
            prev_close_elem = row.select_one('.prev-close, .previous-close, .prev-day')
            
            if name_elem:
                index_data = {
                    'name': name_elem.text.strip(),
                    'change': change_elem.text.strip() if change_elem else '',
                    'high': high_elem.text.strip() if high_elem else '',
                    'low': low_elem.text.strip() if low_elem else '',
                    'open': open_elem.text.strip() if open_elem else '',
                    'prev_close': prev_close_elem.text.strip() if prev_close_elem else '',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                indices_data.append(index_data)
    
    return indices_data

def scrape_groww_global_indices(use_selenium=False):
    """
    Scrape global indices data from Groww website.
    
    Args:
        use_selenium (bool): Whether to use Selenium for JavaScript rendering
    
    Returns:
        list: List of dictionaries containing indices data
    """
    # Try to fetch data directly from the API first
    data = fetch_from_api()
    if data:
        indices_data = process_json_data(data)
        if indices_data:
            logger.info(f"Successfully extracted {len(indices_data)} indices from API")
            return indices_data
    
    # If API didn't work, try fetching the page
    page_content = None
    if use_selenium:
        page_content = fetch_with_selenium()
    
    if not page_content:
        page_content = fetch_with_requests()
    
    if not page_content:
        logger.error("Failed to fetch page content")
        return []
    
    # Parse the page content
    soup = BeautifulSoup(page_content, 'html.parser')
    
    # Try to extract data from script tags
    data = extract_from_script_tags(soup)
    if data:
        indices_data = process_json_data(data)
        if indices_data:
            logger.info(f"Successfully extracted {len(indices_data)} indices from script tags")
            return indices_data
    
    # Last resort - extract from HTML
    indices_data = extract_from_html(soup)
    if indices_data:
        logger.info(f"Successfully extracted {len(indices_data)} indices from HTML")
        return indices_data
    
    logger.error("No indices data found")
    return []

@app.route('/api/scrape', methods=['GET'])
def api_scrape():
    """API endpoint to scrape the Groww website."""
    try:
        # Get parameters from query string
        use_selenium = request.args.get('selenium', 'false').lower() == 'true'
        store_in_db = request.args.get('store_db', 'true').lower() == 'true'
        limit = int(request.args.get('limit', '100'))
        use_limit = request.args.get('use_limit', 'true').lower() == 'true'
        
        # MongoDB configuration
        mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb+srv://dbusername:dbpassword@cluster0.sethv79.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
        mongodb_db = os.environ.get('MONGODB_DB', 'test')
        mongodb_collection = os.environ.get('MONGODB_COLLECTION', 'global_indices')
        
        # Scrape the data
        indices_data = scrape_groww_global_indices(use_selenium=use_selenium)
        
        # Connect to MongoDB and store the data if required
        if store_in_db and indices_data:
            mongodb_client, mongodb_collection_obj = connect_to_mongodb(
                mongodb_uri, 
                mongodb_db, 
                mongodb_collection
            )
            
            if mongodb_collection_obj is not None:
                store_data_in_mongodb(
                    indices_data, 
                    mongodb_collection_obj, 
                    use_limit=use_limit, 
                    limit=limit
                )
                
                # Fetch the data from MongoDB to ensure we're not returning data with ObjectId
                # This ensures we get the data with proper JSON serialization
                cursor = mongodb_collection_obj.find({}, {'_id': 0})
                indices_data = list(cursor)
                
                # Convert datetime objects to ISO format strings for JSON serialization
                for item in indices_data:
                    if 'timestamp' in item and isinstance(item['timestamp'], datetime):
                        item['timestamp'] = item['timestamp'].isoformat()
                
                # Close MongoDB connection
                if mongodb_client is not None:
                    mongodb_client.close()
                    logger.info("MongoDB connection closed")
        
        # Return the data as JSON
        return jsonify({
            'success': True,
            'message': f'Successfully scraped {len(indices_data)} indices',
            'count': len(indices_data),
            'indices': indices_data
        })
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}",
            'data': []
        }), 500

@app.route('/api/healthcheck', methods=['GET'])
def healthcheck():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint."""
    return jsonify({
        'name': 'Groww Global Indices Scraper API',
        'description': 'API to scrape global indices data from Groww website',
        'endpoints': {
            '/api/scrape': 'Scrape the Groww website and return the data',
            '/api/data': 'Get data from MongoDB with option to scrape fresh data first',
            '/api/healthcheck': 'Health check endpoint'
        },
        'parameters': {
            'selenium': 'true/false - Whether to use Selenium (default: false)',
            'store_db': 'true/false - Whether to store in MongoDB (default: true)',
            'limit': 'Number of records to keep in MongoDB (default: 100)',
            'use_limit': 'true/false - Whether to limit records (default: true)',
            'scrape_first': 'true/false - Whether to scrape fresh data before returning results (default: true)'
        }
    })

@app.route('/api/data', methods=['GET'])
def get_data():
    """API endpoint to fetch stored data with option to scrape fresh data first."""
    try:
        # Get parameters from query string
        scrape_first = request.args.get('scrape_first', 'true').lower() == 'true'
        use_selenium = request.args.get('selenium', 'false').lower() == 'true'
        store_in_db = request.args.get('store_db', 'true').lower() == 'true'
        limit = int(request.args.get('limit', '100'))
        use_limit = request.args.get('use_limit', 'true').lower() == 'true'
        
        # MongoDB configuration
        mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb+srv://dbusername:dbpassword@cluster0.sethv79.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
        mongodb_db = os.environ.get('MONGODB_DB', 'test')
        mongodb_collection = os.environ.get('MONGODB_COLLECTION', 'global_indices')
        
        # Connect to MongoDB
        mongodb_client, collection = connect_to_mongodb(mongodb_uri, mongodb_db, mongodb_collection)
        
        if collection is None:
            return jsonify({
                'success': False,
                'message': 'Failed to connect to MongoDB',
                'data': []
            }), 500
        
        # Scrape fresh data if requested
        if scrape_first:
            logger.info("Scraping fresh data before returning results")
            indices_data = scrape_groww_global_indices(use_selenium=use_selenium)
            
            if store_in_db and indices_data:
                store_data_in_mongodb(
                    indices_data, 
                    collection, 
                    use_limit=use_limit, 
                    limit=limit
                )
        
        # Fetch data from MongoDB, sort by timestamp descending
        cursor = collection.find({}, {'_id': 0}).sort('timestamp', -1)
        data = list(cursor)
        
        # Convert datetime objects to ISO format strings for JSON serialization
        for item in data:
            if 'timestamp' in item and isinstance(item['timestamp'], datetime):
                item['timestamp'] = item['timestamp'].isoformat()
        
        # Close MongoDB connection
        if mongodb_client is not None:
            mongodb_client.close()
        
        return jsonify({
            'success': True,
            'count': len(data),
            'data': data
        })
    
    except Exception as e:
        logger.error(f"Data retrieval error: {e}")
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}",
            'data': []
        }), 500

@app.route('/api/raw_data', methods=['GET'])
def api_raw_data():
    """API endpoint to get raw unfiltered data from Groww website without storing in database."""
    try:
        # Get parameter from query string
        use_selenium = request.args.get('selenium', 'false').lower() == 'true'
        
        # Try to fetch data directly from the API first
        raw_data = fetch_from_api()
        
        # If API didn't work, try fetching the page
        if not raw_data:
            page_content = None
            if use_selenium:
                page_content = fetch_with_selenium()
            
            if not page_content:
                page_content = fetch_with_requests()
            
            if not page_content:
                return jsonify({
                    'success': False,
                    'message': 'Failed to fetch page content',
                    'data': None
                }), 500
            
            # Parse the page content
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Try to extract data from script tags
            raw_data = extract_from_script_tags(soup)
            
            # If no script data, return text content
            if not raw_data:
                raw_data = {
                    'html_content': soup.get_text(),
                    'html_structure': str(soup)[:10000] + '...' if len(str(soup)) > 10000 else str(soup)
                }
        
        return jsonify({
            'success': True,
            'message': 'Successfully retrieved raw data',
            'data': raw_data
        })
    except Exception as e:
        logger.error(f"Raw data API error: {e}")
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}",
            'data': None
        }), 500

# For local testing
if __name__ == '__main__':
    app.run(debug=True) 