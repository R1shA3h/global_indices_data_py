# Global Indices Data Collector

This script fetches global index closing prices daily at 2 AM IST and stores them in MongoDB.

## Setup

1. Install dependencies:
   ```
   npm install axios mongoose node-cron moment-timezone date-holidays dotenv express
   ```

2. Create a `.env` file in the root directory with the following contents:
   ```
   # MongoDB Connection String
   MONGODB_URI=mongodb+srv://yourusername:yourpassword@yourcluster.mongodb.net/?retryWrites=true&w=majority

   # API URL for fetching index data
   ```

3. Replace the MongoDB connection string with your actual database credentials.

## Running the Script

### Normal Mode
```
node index.js
```
- Connects to MongoDB
- Schedules a daily job at 2 AM IST
- Starts an Express server on port 3000

### Test Mode
```
node index.js --test
```
- Shows the data that would be saved without connecting to MongoDB
- Useful for debugging and verifying the format

## PM2 Deployment
```
pm2 start index.js --name global-indices
```

## Features

- Fetches data for multiple global indices
- Handles holidays, retries, and duplicate checks
- Stores data in the expected MongoDB format
- Includes an API to query the stored data 