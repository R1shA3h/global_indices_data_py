module.exports = {
  apps: [
    {
      name: 'global-indices',
      script: 'index.js',
      description: 'Global indices data collector with integrated API server',
      
      // Environment variables
      env: {
        NODE_ENV: 'production',
        TZ: 'Asia/Kolkata'
        // MONGODB_URI and API_URL are loaded from .env file
      },
      
      // Restart policy
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      
      // Logging
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: 'logs/error.log',
      out_file: 'logs/output.log',
      merge_logs: true,
      
      // Run a single instance
      instances: 1,
      exec_mode: 'fork',
      
      // Wait for ready signal
      wait_ready: true,
      listen_timeout: 30000,
      
      // Additional options
      restart_delay: 3000,
      kill_timeout: 5000
    }
  ]
}; 