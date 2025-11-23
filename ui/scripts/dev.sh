#!/bin/bash
# Development startup script for MX Repair Desktop

echo "================================================"
echo "  MX Repair Desktop - Development Mode"
echo "================================================"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

echo "🚀 Starting development servers..."
echo ""
echo "  Next.js:  http://localhost:3000"
echo "  Electron: Opening desktop app..."
echo ""
echo "Press Ctrl+C to stop"
echo ""

npm run electron:dev

