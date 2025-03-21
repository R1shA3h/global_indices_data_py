# Groww Global Indices Scraper API

A serverless API that scrapes global indices data from Groww website and stores it in MongoDB.

## Deployment on Vercel

This API is designed to be deployed on Vercel, a serverless platform. Here's how to deploy it:

1. Clone this repository
2. Sign up for a [Vercel account](https://vercel.com/signup) if you don't have one already
3. Install the Vercel CLI: `npm install -g vercel`
4. Deploy with: `vercel`

## Environment Variables

Set these environment variables in your Vercel dashboard:

- `MONGODB_URI`: Your MongoDB connection string
- `MONGODB_DB`: Database name (default: "test")
- `MONGODB_COLLECTION`: Collection name (default: "global_indices")

## API Endpoints

### Scrape Data: `/api/scrape`

Scrapes global indices data from Groww website and optionally stores it in MongoDB.

Query parameters:
- `selenium`: Whether to use Selenium (default: false)
- `store_db`: Whether to store data in MongoDB (default: true)
- `limit`: Number of records to keep in MongoDB (default: 100)
- `use_limit`: Whether to limit the number of records (default: true)

Example:
```
https://your-vercel-app.vercel.app/api/scrape?selenium=false&limit=100
```

### Health Check: `/api/healthcheck`

Checks if the API is running.

Example:
```
https://your-vercel-app.vercel.app/api/healthcheck
```

## Scheduling Scraping

Since Vercel doesn't support built-in scheduling, use one of these methods:

1. **Cron Job Service**: Use a service like [cron-job.org](https://cron-job.org) to call your API endpoint at regular intervals.

2. **GitHub Actions**: Set up a GitHub workflow to call your API endpoint at regular intervals.

3. **Other Services**: Use AWS Lambda, Google Cloud Functions, or Azure Functions with their respective scheduling services.

Example GitHub Actions workflow:

```yaml
name: Scrape Groww Indices

on:
  schedule:
    - cron: '0 */6 * * *'  # Run every 6 hours

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - name: Call API endpoint
        run: |
          curl -X GET "https://your-vercel-app.vercel.app/api/scrape"
```

## Local Development

To run the API locally:

1. Install dependencies: `pip install -r requirements.txt`
2. Run the app: `python api/index.py`
3. Visit: `http://localhost:5000`

## Data Structure

The scraped data is stored in MongoDB with the following structure:

```json
{
  "_id": "ObjectId(...)",
  "name": "Dow Jones",
  "symbol": "DJI",
  "country": "USA",
  "price": "41,985.63",
  "change": "383.32",
  "timestamp": "2023-05-20T12:34:56.789Z"
}
```

Note: The "change_percent" field has been removed as requested. 