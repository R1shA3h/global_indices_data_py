# Groww Global Indices Scraper API

A serverless API that scrapes global indices data from Groww website and stores it in MongoDB. Built with Flask and deployed on DigitalOcean.

## Features

- Scrapes global indices data from [Groww](https://groww.in/indices/global-indices)
- Multiple data extraction methods:
  - Direct API requests
  - HTML parsing
  - Selenium support for JavaScript-rendered content
- MongoDB integration for data storage
- RESTful API endpoints
- Production-ready with Gunicorn and Nginx

## API Endpoints

### 1. Scrape Data
```
GET /api/scrape
```
Scrapes global indices data from Groww website and optionally stores it in MongoDB.

Query Parameters:
- `selenium`: Whether to use Selenium (default: false)
- `store_db`: Whether to store data in MongoDB (default: true)
- `limit`: Number of records to keep in MongoDB (default: 100)
- `use_limit`: Whether to limit the number of records (default: true)

Example:
```bash
curl "http://your-domain/api/scrape?selenium=false&limit=100"
```

### 2. Get Stored Data
```
GET /api/data
```
Retrieves the stored indices data from MongoDB.

Example:
```bash
curl "http://your-domain/api/data"
```

### 3. Health Check
```
GET /api/healthcheck
```
Checks if the API is running.

Example:
```bash
curl "http://your-domain/api/healthcheck"
```

## Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd global_indices_scrapper_py
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
export MONGODB_URI="your_mongodb_uri"
export MONGODB_DB="test"
export MONGODB_COLLECTION="global_indices"
```

5. Run the development server:
```bash
python api/index.py
```

The API will be available at `http://localhost:5000`

## Production Deployment

### Prerequisites
- Python 3.7+
- MongoDB
- Nginx
- Gunicorn

### Server Setup

1. Install system dependencies:
```bash
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv nginx -y
```

2. Clone the repository:
```bash
git clone <repository-url>
cd global_indices_scrapper_py
```

3. Set up Python environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. Configure systemd service:
```bash
nano /etc/systemd/system/groww_scraper.service
```

Add:
```ini
[Unit]
Description=Groww Scraper API
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/global_indices_scrapper_py/global_indices_data_py
Environment="PATH=/root/global_indices_scrapper_py/global_indices_data_py/venv/bin"
Environment="MONGODB_URI=your_mongodb_uri"
Environment="MONGODB_DB=test"
Environment="MONGODB_COLLECTION=global_indices"
ExecStart=/root/global_indices_scrapper_py/global_indices_data_py/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 api.index:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

5. Configure Nginx:
```bash
nano /etc/nginx/global_indices_scrapper_py/groww_scraper
```

Add:
```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location / {
        return 404;
    }
}
```

6. Enable the site:
```bash
ln -s /etc/nginx/global_indices_scrapper_py/groww_scraper /etc/nginx/sites-enabled/
```

7. Start services:
```bash
systemctl daemon-reload
systemctl start groww_scraper
systemctl enable groww_scraper
systemctl restart nginx
```

## Data Structure

The scraped data is stored in MongoDB with the following structure:
```json
{
    "name": "Dow Jones",
    "symbol": "DJI",
    "country": "USA",
    "price": "41,985.63",
    "change": "383.32",
    "timestamp": "2025-03-27T12:53:57.597088"
}
```

## Monitoring

- Check service status: `systemctl status groww_scraper`
- View application logs: `journalctl -u groww_scraper -f`
- View Nginx logs: `tail -f /var/log/nginx/error.log`

## Security Considerations

1. Use environment variables for sensitive data
2. Implement rate limiting
3. Use HTTPS in production
4. Regularly update dependencies
5. Monitor server logs for suspicious activity

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the repository or contact the maintainers. 