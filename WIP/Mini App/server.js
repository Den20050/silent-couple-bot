const express = require('express');
const crypto = require('crypto');
const path = require('path');
const rateLimit = require('express-rate-limit');
const helmet = require('helmet');

const app = express();

// Environment variables
const BOT_TOKEN = process.env.TG_BOT_TOKEN;
const PORT = process.env.MINI_APP_PORT || 3000;
const NODE_ENV = process.env.NODE_ENV || 'production';

// Security middlewares
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'", "'unsafe-inline'", "https://telegram.org"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            imgSrc: ["'self'", "data:", "https://api.telegram.org"],
            connectSrc: ["'self'", "https://api.telegram.org"],
        },
    },
    referrerPolicy: { policy: "no-referrer" },
}));

// Rate limiting: 60 requests per minute per IP
const limiter = rateLimit({
    windowMs: 60 * 1000, // 1 minute
    max: 60,
    message: { error: 'Too many requests, please try again later' },
    standardHeaders: true,
    legacyHeaders: false,
});
app.use(limiter);

// Trust proxy (Cloudflare)
app.set('trust proxy', 1);

// Static files
app.use(express.static(path.join(__dirname), {
    dotfiles: 'deny',
    index: false,
    maxAge: '1d'
}));

// Telegram initData verification function
function verifyTelegramInitData(initData) {
    if (!initData) return false;
    
    try {
        const params = new URLSearchParams(initData);
        const hash = params.get('hash');
        params.delete('hash');
        
        // Sort params alphabetically
        const dataCheckString = Array.from(params.keys())
            .sort()
            .map(key => `${key}=${params.get(key)}`)
            .join('\n');
        
        const secretKey = crypto.createHmac('sha256', 'WebAppData')
            .update(BOT_TOKEN)
            .digest();
        
        const calculatedHash = crypto.createHmac('sha256', secretKey)
            .update(dataCheckString)
            .digest('hex');
        
        return calculatedHash === hash;
    } catch (error) {
        console.error('Verification error:', error);
        return false;
    }
}

// API endpoint for verification
app.get('/api/verify', (req, res) => {
    const { initData } = req.query;
    
    if (!initData) {
        return res.status(400).json({ verified: false, error: 'No initData provided' });
    }
    
    const isValid = verifyTelegramInitData(initData);
    
    if (!isValid) {
        // Log security event
        console.warn(`Invalid initData from IP: ${req.ip}`);
        return res.status(403).json({ verified: false, error: 'Invalid signature' });
    }
    
    res.json({ verified: true });
});

// Health check
app.get('/health', (req, res) => {
    if (!BOT_TOKEN) {
        return res.status(500).json({ status: 'error', message: 'BOT_TOKEN not set' });
    }
    
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        environment: NODE_ENV
    });
});

// Error handling
app.use((err, req, res, next) => {
    console.error('Unhandled error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// 404 handler
app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully...');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.log('SIGINT received, shutting down gracefully...');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});

// Start server
const server = app.listen(PORT, () => {
    console.log(`🔥 Mini App server running on port ${PORT} (${NODE_ENV} mode)`);
    console.log(`📍 Health check: http://localhost:${PORT}/health`);
});

module.exports = app; // For testing