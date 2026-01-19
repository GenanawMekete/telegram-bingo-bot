// Configuration for different environments
const CONFIG = {
  development: {
    BACKEND_URL: "http://localhost:5000",
    SOCKET_PATH: "/socket.io"
  },
  production: {
    BACKEND_URL: "https://your-backend-service.onrender.com",
    SOCKET_PATH: "/socket.io"
  }
};

// Auto-detect environment
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
const currentConfig = isProduction ? CONFIG.production : CONFIG.development;

// Export configuration
window.APP_CONFIG = currentConfig;
