/*
  Node.js script for fetching global index closing prices daily at 2 AM IST,
  handling edge-cases (holidays, retries, duplicates) and storing in MongoDB.

  - Run under PM2 on DigitalOcean: `pm2 start index.js --name global-indices`
  - Test mode: `node index.js --test` (shows data format without saving to DB)
*/

// Load environment variables from .env file
require('dotenv').config();

// Set the default timezone
process.env.TZ = 'Asia/Kolkata';

const axios = require('axios');
const mongoose = require('mongoose');
const cron = require('node-cron');
const moment = require('moment-timezone');
const Holidays = require('date-holidays');

// Check for test mode
const isTestMode = process.argv.includes('--test');
console.log(isTestMode ? 'RUNNING IN TEST MODE - No data will be saved to DB' : 'Running in normal mode');

// Holiday calendar for relevant markets
const hdIN = new Holidays('IN');
const hdUS = new Holidays('US');
const hdJP = new Holidays('JP');
const hdGB = new Holidays('GB');
const hdHK = new Holidays('HK');
const hdDE = new Holidays('DE');
const hdFR = new Holidays('FR');
const hdKR = new Holidays('KR');

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

// MongoDB setup with connection string from environment variables
let CloseModel;
if (!isTestMode) {
  mongoose.connect(process.env.MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true });
  const closeSchema = new mongoose.Schema({
    index: String,
    date: Date,
    close: Number
  });
  CloseModel = mongoose.model('global_indices_historical_data', closeSchema);
  console.log(`Connected to MongoDB Atlas`);
} else {
  console.log(`MongoDB connection skipped in test mode`);
}

// Uncaught exceptions -> exit and let PM2 restart
process.on('uncaughtException', err => {
  console.error('Uncaught Exception:', err);
  process.exit(1);
});
process.on('unhandledRejection', err => {
  console.error('Unhandled Rejection:', err);
  process.exit(1);
});

// Index definitions (key must match API name prefix)
const indices = [
  { key: 'gift-nifty', label: 'GIFT NIFTY', holidayCalendar: hdIN },
  { key: 'dow',        label: 'Dow',        holidayCalendar: hdUS },
  { key: 'nasdaq',     label: 'NASDAQ',     holidayCalendar: hdUS },
  { key: 'sandp',      label: 'S&P',        holidayCalendar: hdUS },
  { key: 'nikkei',     label: 'NIKKEI',     holidayCalendar: hdJP },
  { key: 'hang',       label: 'HANG SENG',  holidayCalendar: hdHK },
  { key: 'dax',        label: 'DAX',        holidayCalendar: hdDE },
  { key: 'cac',        label: 'CAC',        holidayCalendar: hdFR },
  { key: 'ftse',       label: 'FTSE 100',   holidayCalendar: hdGB },
  { key: 'kospi',      label: 'KOSPI',      holidayCalendar: hdKR }
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

// Generate a MongoDB ObjectId for test mode
function generateMockObjectId() {
  const timestamp = Math.floor(new Date().getTime() / 1000).toString(16).padStart(8, '0');
  const randomPart = [...Array(16)].map(() => Math.floor(Math.random() * 16).toString(16)).join('');
  return timestamp + randomPart;
}

// Function to fetch and store all indices data
async function fetchAndStoreIndicesData() {
  console.log(`Running ${isTestMode ? 'TEST' : 'daily'} indices data collection at ${new Date().toISOString()}`);
  
  try {
    const res = await fetchWithRetry(process.env.API_URL);
    if (!res.data.success || !Array.isArray(res.data.data)) {
      throw new Error('Invalid API response shape');
    }
    
    console.log('=== FETCHING INDICES DATA ===');
    const apiData = res.data.data;
    
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
    
    // Array to collect formatted records for test mode
    const testModeRecords = [];
    
    // Process each index
    for (const { key, label, holidayCalendar } of indices) {
      const entry = findEntry(apiData, label);
      if (!entry) {
        console.warn(`${label}: Not found in API response`);
        continue;
      }
      
      console.log(`Processing ${label}: ${entry.prev_close}`);
      
      // Skip if holiday (check previous day)
      if (holidayCalendar.isHoliday(yesterday.toDate())) {
        console.log(`${label} trading day ${yesterday.format('YYYY-MM-DD')} is a holiday, skipping.`);
        continue;
      }
      
      // Parse close price robustly
      const raw = entry.prev_close;
      const parsed = parseFloat(raw.replace(/[^0-9.]/g, ''));
      if (isNaN(parsed)) {
        console.error(`Cannot parse close price '${raw}' for ${label}`);
        continue;
      }
      const closeVal = parsed;
      
      if (!isTestMode) {
        // Check for duplicates - only in normal mode
        const last = await CloseModel.findOne({ index: key }).sort({ date: -1 });
        if (last && 
            last.date.toISOString().split('T')[0] === prevISODate.split('T')[0] && 
            last.close === closeVal) {
          console.log(`${key} unchanged on ${prevISODate.split('T')[0]}, skipping.`);
          continue;
        }
        
        // Create Date object just for storage
        const dateForStorage = new Date(prevISODate);
        
        // Upsert document
        await CloseModel.updateOne(
          { index: key, date: dateForStorage },
          { $set: { close: closeVal } },
          { upsert: true }
        );
        console.log(`Stored ${key} @ ${prevISODate} = ${closeVal}`);
      } else {
        // In test mode, just format and collect the data
        const mockRecord = {
          _id: {
            $oid: generateMockObjectId()
          },
          index: key,
          date: {
            $date: prevISODate
          },
          close: closeVal
        };
        
        testModeRecords.push(mockRecord);
      }
    }
    
    // In test mode, display the records that would be saved
    if (isTestMode && testModeRecords.length > 0) {
      console.log('\n=== TEST MODE: DATA FORMAT THAT WOULD BE SAVED ===');
      console.log(JSON.stringify(testModeRecords, null, 2));
      console.log('===================================================\n');
    }
    
    console.log('=== COMPLETED DATA COLLECTION ===');
    return testModeRecords;
  } catch (err) {
    console.error('Error in data collection:', err.message);
    return [];
  }
}

// Show current indices data at startup
async function showCurrentIndicesData() {
  try {
    const res = await fetchWithRetry(process.env.API_URL);
    if (!res.data.success || !Array.isArray(res.data.data)) {
      throw new Error('Invalid API response shape');
    }
    
    console.log('\n=== CURRENT INDICES DATA ===');
    
    // Process each index
    for (const { key, label } of indices) {
      const entry = findEntry(res.data.data, label);
      if (entry) {
        console.log(`${label}: ${entry.prev_close}`);
      } else {
        console.log(`${label}: Not found in API response`);
      }
    }
    
    console.log('===========================\n');
  } catch (err) {
    console.error('Error fetching current data:', err.message);
  }
}

// Show current data at startup if not in test mode
if (!isTestMode) {
  showCurrentIndicesData();
  
  // Schedule daily job at 2:00 AM IST
  cron.schedule('0 2 * * *', fetchAndStoreIndicesData, {
    timezone: 'Asia/Kolkata'
  });
  
  console.log('Scheduled daily job to run at 2:00 AM IST');
  
  // Optional: Express API to retrieve stored closes
  const express = require('express');
  const app = express();
  
  // Get all data
  app.get('/closes', async (req, res) => {
    try {
      const docs = await CloseModel.find().sort({ date: -1, index: 1 }).lean();
      res.json(docs);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });
  
  // Get data for a specific index
  app.get('/closes/:index', async (req, res) => {
    try {
      const docs = await CloseModel
        .find({ index: req.params.index })
        .sort({ date: -1 })
        .lean();
      res.json(docs);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });
  
  // Manual trigger endpoint
  app.get('/trigger', async (req, res) => {
    try {
      await fetchAndStoreIndicesData();
      res.json({ success: true, message: 'Triggered data collection' });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });
  
  app.listen(3000, () => console.log('HTTP API listening on port 3000'));
} else {
  // In test mode, just run once and exit
  (async () => {
    await fetchAndStoreIndicesData();
    console.log('Test completed. Exiting...');
  })();
} 