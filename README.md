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
   API_URL=http://143.110.182.215/api/data
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

### One-time Save Mode
```
node save_entry.js
```
- Runs once and saves a single entry to the database
- Displays the saved entry with its MongoDB ID
- Automatically closes the connection after saving

### Cleanup Script
```
node cleanup_collections.js
```
- Migrates data from the incorrectly named "global_indices_historical_datas" collection to the correct "global_indices_historical_data" collection
- Useful if you had data previously saved with the incorrect collection name due to Mongoose's automatic pluralization
- Only run this once to fix collection naming issues

## PM2 Deployment

### Simple Deployment
```
pm2 start index.js --name global-indices
```

### Using PM2 Ecosystem File (Recommended)
We've included a PM2 ecosystem config file for better process management:

```
# Start the application
pm2 start ecosystem.config.js

# Other useful PM2 commands
pm2 status                  # Check status
pm2 logs global-indices     # View logs
pm2 restart global-indices  # Restart the app
pm2 stop global-indices     # Stop the app
pm2 delete global-indices   # Remove from PM2

# Save the PM2 configuration to run on system startup
pm2 save
pm2 startup
```

The ecosystem file provides:
- Proper logging configuration
- Environment variables
- Automatic restart settings
- Resource limits

## Features

- Fetches data for multiple global indices
- Handles holidays, retries, and duplicate checks
- Stores data in the expected MongoDB format
- Includes an API to query the stored data

## Data Format

Data is stored in MongoDB with the following format:
```json
{
  "_id": {
    "$oid": "681c61b9f7bda9baeae87507"
  },
  "index": "gift-nifty",
  "date": {
    "$date": "2025-05-07T00:00:00.000Z"
  },
  "close": 23120
}
```

## Troubleshooting

### Collection Names
By default, Mongoose automatically pluralizes collection names. This script explicitly sets the collection name to `global_indices_historical_data` to prevent the automatic pluralization to `global_indices_historical_datas`.

If you find your data in the wrong collection, use the cleanup script to migrate it:
```
node cleanup_collections.js
```

### Removing __v field from documents
Mongoose automatically adds a `__v` field to documents for versioning purposes. We've updated the schemas to prevent this, but for existing documents with `__v` field, you can run the following code to remove it:

Create a file named `remove_version_field.js` with this content:

```javascript
// Load environment variables from .env file
require('dotenv').config();

const mongoose = require('mongoose');

// Connect to MongoDB
mongoose.connect(process.env.MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('Connected to MongoDB'))
  .catch(err => console.error(`MongoDB connection error: ${err.message}`));

async function removeVersionField() {
  try {
    // Get native collection object
    const collection = mongoose.connection.db.collection('global_indices_historical_data');
    
    // Count documents with __v field
    const countWithVersion = await collection.countDocuments({ __v: { $exists: true } });
    console.log(`Found ${countWithVersion} documents with __v field`);
    
    // Remove __v field from all documents
    const result = await collection.updateMany(
      { __v: { $exists: true } },
      { $unset: { __v: "" } }
    );
    
    console.log(`Updated ${result.modifiedCount} documents`);
  } catch (err) {
    console.error('Error:', err);
  } finally {
    mongoose.connection.close();
  }
}

removeVersionField();
```

Then run:
```
node remove_version_field.js
``` 