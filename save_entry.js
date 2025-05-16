/*
  Script to fetch and save a single entry to the database
  Run with: node save_entry.js
*/

// Load environment variables from .env file
require('dotenv').config();

// Set the default timezone
process.env.TZ = 'Asia/Kolkata';

const axios = require('axios');
const mongoose = require('mongoose');
const moment = require('moment-timezone');

// Verify required environment variables
if (!process.env.MONGODB_URI) {
  console.error('Missing required environment variable: MONGODB_URI');
  process.exit(1);
}

if (!process.env.API_URL) {
  console.error('Missing required environment variable: API_URL');
  process.exit(1);
}

// Retry helper for HTTP
async function fetchWithRetry(url, attempts = 3, delayMs = 1000) {
  for (let i = 1; i <= attempts; i++) {
    try {
      return await axios.get(url);
    } catch (err) {
      if (i === attempts) throw err;
      console.warn(`Fetch attempt ${i} failed, retrying in ${delayMs}ms...`);
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}

// MongoDB setup
mongoose.connect(process.env.MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log(`Successfully connected to MongoDB Atlas`))
  .catch(err => {
    console.error(`MongoDB connection error: ${err.message}`);
    process.exit(1);
  });

// Log the actual connection string (with password masked for security)
const maskedURI = process.env.MONGODB_URI.replace(
  /mongodb(\+srv)?:\/\/[^:]+:([^@]+)@/,
  'mongodb$1://******:******@'
);
console.log(`Using MongoDB URI: ${maskedURI}`);

// Create schema with options to hide __v field
const closeSchema = new mongoose.Schema(
  {
    index: String,
    date: Date,
    close: Number
  },
  { 
    versionKey: false // This removes the __v field completely
  }
);

// Log the collection name being used
const collectionName = 'global_indices_historical_data';
console.log(`Using collection: ${collectionName}`);

// Create the model with explicit collection name to prevent pluralization
const CloseModel = mongoose.model('GlobalIndicesData', closeSchema, collectionName);

// Update indices array to remove holidayCalendar
const indices = [
  { key: 'gift-nifty', label: 'GIFT NIFTY' },
  { key: 'dow',        label: 'Dow' },
  { key: 'nasdaq',     label: 'NASDAQ' },
  { key: 'sandp',      label: 'S&P' },
  { key: 'nikkei',     label: 'NIKKEI' },
  { key: 'hang',       label: 'HANG SENG' },
  { key: 'dax',        label: 'DAX' },
  { key: 'cac',        label: 'CAC' },
  { key: 'ftse',       label: 'FTSE 100' },
  { key: 'kospi',      label: 'KOSPI' }
];

// Improved function to find an entry in the API data
function findEntry(data, searchLabel) {
  // Special case for Dow since it has a unique format
  if (searchLabel === "DOW" || searchLabel === "Dow") {
    const dowEntry = data.find(entry => 
      entry.name.toLowerCase().startsWith("dow") // Starting with "dow"
    );
    
    if (dowEntry) {
      return dowEntry;
    }
  }
  
  // Try direct matching first (checking if name starts with label)
  const exactMatch = data.find(e => {
    const nameUpperCase = e.name.toUpperCase();
    return nameUpperCase.startsWith(searchLabel);
  });
  
  if (exactMatch) return exactMatch;
  
  // Try contains matching as a fallback
  const containsMatch = data.find(e => {
    const containsLabel = e.name.toUpperCase().includes(searchLabel);
    return containsLabel;
  });
  
  return containsMatch || null;
}

// Function to fetch and store a single entry
async function saveEntry() {
  console.log(`Running one-time data save at ${new Date().toISOString()}`);
  
  try {
    // Verify we can query the database first
    try {
      const count = await CloseModel.countDocuments();
      console.log(`Database check: found ${count} existing documents in collection`);
    } catch (dbErr) {
      console.error(`Error checking database: ${dbErr.message}`);
    }
    
    const res = await fetchWithRetry(process.env.API_URL);
    if (!res.data.success || !Array.isArray(res.data.data)) {
      throw new Error('Invalid API response shape');
    }
    
    console.log('=== FETCHING INDICES DATA ===');
    const apiData = res.data.data;
    console.log(`API returned ${apiData.length} entries`);
    
    // Get current date in IST
    const now = moment().tz('Asia/Kolkata');
    console.log(`Current date in IST: ${now.format('YYYY-MM-DD')}`);
    
    // Calculate previous day in IST timezone
    const yesterday = now.clone().subtract(1, 'day').startOf('day');
    console.log(`Previous day in IST: ${yesterday.format('YYYY-MM-DD')}`);
    
    // Create a properly formatted ISO date string - force the date to be at midnight UTC
    // Format the date manually to ensure no timezone issues
    const prevISODate = `${yesterday.format('YYYY-MM-DD')}T00:00:00.000Z`;
    console.log(`Previous day formatted for MongoDB: ${prevISODate}`);
    
    // Save counter
    let savedCount = 0;
    
    // Process each index
    for (const { key, label } of indices) {
      const entry = findEntry(apiData, label);
      if (!entry) {
        console.warn(`${label}: Not found in API response`);
        continue;
      }
      console.log(`Processing ${label}: ${entry.prev_close}`);
      // Parse close price robustly
      const raw = entry.prev_close;
      const parsed = parseFloat(raw.replace(/[^0-9.]/g, ''));
      if (isNaN(parsed)) {
        console.error(`Cannot parse close price '${raw}' for ${label}`);
        continue;
      }
      const closeVal = parsed;
      // Fetch the most recent DB entry for this index
      const last = await CloseModel.findOne({ index: key }).sort({ date: -1 });
      if (last && last.close === closeVal) {
        console.log(`${key} unchanged from previous value ${last.close} (last recorded on ${last.date.toISOString().split('T')[0]}), skipping.`);
        continue;
      }
      // Only insert if close is different from the most recent entry
      const dateForStorage = new Date(prevISODate);
      const newEntry = new CloseModel({
        index: key,
        date: dateForStorage,
        close: closeVal
      });
      console.log(`Saving document: ${JSON.stringify(newEntry)} (previous value: ${last ? last.close : 'none'})`);
      try {
        const savedDoc = await newEntry.save();
        savedCount++;
        console.log(`Successfully saved ${key} with _id: ${savedDoc._id}`);
      } catch (saveErr) {
        console.error(`Error saving ${key}: ${saveErr.message}`);
        continue;
      }
      // Fetch and display the saved entry
      try {
        const savedEntry = await CloseModel.findOne({ index: key, date: dateForStorage }).lean();
        if (savedEntry) {
          console.log(`\n=== SAVED ENTRY IN DATABASE ===`);
          console.log(JSON.stringify({
            _id: savedEntry._id,
            index: savedEntry.index,
            date: savedEntry.date,
            close: savedEntry.close
          }, null, 2));
          console.log(`===========================\n`);
        } else {
          console.error(`ERROR: Entry for ${key} was saved but could not be retrieved!`);
        }
      } catch (findErr) {
        console.error(`Error finding saved entry for ${key}: ${findErr.message}`);
      }
    }
    
    // Verify final state of the database
    try {
      const finalCount = await CloseModel.countDocuments();
      console.log(`Database final check: now has ${finalCount} documents (added ${savedCount})`);
    } catch (dbErr) {
      console.error(`Error checking final database state: ${dbErr.message}`);
    }
    
    console.log(`=== COMPLETED: SAVED ${savedCount} ENTRIES ===`);
    
  } catch (err) {
    console.error('Error saving entries:', err.message);
    if (err.stack) console.error(err.stack);
  } finally {
    // Close the MongoDB connection
    try {
      await mongoose.connection.close();
      console.log('MongoDB connection closed');
    } catch (closeErr) {
      console.error(`Error closing MongoDB connection: ${closeErr.message}`);
    }
  }
}

// Run the function immediately
saveEntry(); 