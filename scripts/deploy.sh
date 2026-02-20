#!/bin/bash
# Deploy to Vercel

set -e

echo "🚀 Desplegando a Vercel..."

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "📦 Installing Vercel CLI..."
    npm install -g vercel
fi

# Deploy
vercel --prod --yes

echo "✅ Despliegue completado!"
