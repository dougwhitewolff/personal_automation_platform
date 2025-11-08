#!/bin/bash
# Quick verification script for Personal Automation Platform

echo "=================================="
echo "  File Verification Script"
echo "=================================="
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Not in personal-automation-platform directory"
    echo "   Please run this from inside the extracted folder"
    exit 1
fi

# Count files
file_count=$(find . -type f | wc -l)
echo "📄 Files found: $file_count (expected: 28)"

if [ "$file_count" -eq 28 ]; then
    echo "   ✅ File count correct!"
else
    echo "   ⚠️  File count mismatch - some files may be missing"
fi

echo ""

# Check directories
echo "📁 Checking directories..."
for dir in core modules deployment utils; do
    if [ -d "$dir" ]; then
        echo "   ✅ $dir/ exists"
    else
        echo "   ❌ $dir/ missing!"
    fi
done

echo ""

# Check critical documentation
echo "📖 Checking documentation..."
for doc in INDEX.md PROJECT_SUMMARY.md QUICKSTART.md README.md DEPLOYMENT.md CONTRIBUTING.md; do
    if [ -f "$doc" ]; then
        echo "   ✅ $doc"
    else
        echo "   ❌ $doc missing!"
    fi
done

echo ""

# Check configuration
echo "⚙️  Checking configuration..."
for file in config.yaml .env.example requirements.txt; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file missing!"
    fi
done

echo ""

# Check modules
echo "🔌 Checking modules..."
if [ -f "modules/nutrition.py" ] && [ -f "modules/workout.py" ]; then
    echo "   ✅ Both modules present"
else
    echo "   ❌ Module files missing!"
fi

echo ""

# Final verdict
echo "=================================="
if [ "$file_count" -eq 28 ] && [ -f "main.py" ] && [ -f "INDEX.md" ]; then
    echo "✅ SUCCESS! All files present."
    echo ""
    echo "Next steps:"
    echo "1. Read INDEX.md for navigation"
    echo "2. Read PROJECT_SUMMARY.md for overview"
    echo "3. Follow QUICKSTART.md to deploy"
else
    echo "⚠️  WARNING: Some files may be missing."
    echo ""
    echo "Solutions:"
    echo "1. Re-download the .tar.gz archive"
    echo "2. Extract with: tar -xzf personal-automation-platform.tar.gz"
    echo "3. Check FILE_MANIFEST.md for complete file list"
fi
echo "=================================="
