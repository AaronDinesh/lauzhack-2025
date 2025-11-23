#!/bin/bash
# Initial setup script for MX Repair Desktop

echo "================================================"
echo "  MX Repair Desktop - Initial Setup"
echo "================================================"
echo ""

# Check Node.js version
NODE_VERSION=$(node --version 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "❌ Node.js is not installed!"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js detected: $NODE_VERSION"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Installation failed!"
    exit 1
fi

echo ""
echo "✅ Dependencies installed successfully!"
echo ""

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "📝 Creating .env.local..."
    echo "NEXT_PUBLIC_MX_BRIDGE_URL=http://127.0.0.1:8000/stream" > .env.local
    echo "✅ Created .env.local"
else
    echo "ℹ️  .env.local already exists"
fi

echo ""
echo "================================================"
echo "  Setup Complete! 🎉"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start the app:"
echo "     npm run electron:dev"
echo ""
echo "  2. (Optional) Start test server:"
echo "     python test-server.py"
echo ""
echo "  3. Read the docs:"
echo "     cat README.md"
echo ""
echo "Happy coding! 🚀"

