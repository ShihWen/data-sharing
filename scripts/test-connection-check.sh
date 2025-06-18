#!/bin/bash

# Test script to demonstrate the connection checking optimization
# This script shows how much time can be saved by checking before creating

set -e

echo "=== Airflow Connection Check Optimization Test ==="
echo "This script demonstrates the time savings from checking connections first"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Make airflow-manager.sh executable
chmod +x ./airflow-manager.sh

echo "1️⃣ Testing connection check (fast operation)..."
start_time=$(date +%s)

if ./airflow-manager.sh check-connections; then
    end_time=$(date +%s)
    check_duration=$((end_time - start_time))
    print_success "Connections already exist - check completed in ${check_duration} seconds"
    echo ""
    print_info "Since connections exist, we can skip the creation step entirely!"
    print_info "This saves the time needed to recreate existing connections and variables."
    echo ""
    print_success "🚀 OPTIMIZATION RESULT: Pipeline stage completed quickly without unnecessary work!"
    
else
    end_time=$(date +%s)
    check_duration=$((end_time - start_time))
    print_warning "Some connections missing - check completed in ${check_duration} seconds"
    echo ""
    print_info "Now we need to create the missing connections..."
    
    echo "2️⃣ Creating connections and variables..."
    creation_start=$(date +%s)
    
    if ./airflow-manager.sh connections; then
        creation_end=$(date +%s)
        creation_duration=$((creation_end - creation_start))
        total_duration=$((creation_end - start_time))
        
        print_success "Connections created successfully in ${creation_duration} seconds"
        print_info "Total time: ${total_duration} seconds (${check_duration}s check + ${creation_duration}s creation)"
        echo ""
        print_success "✅ All connections and variables are now properly configured!"
    else
        print_warning "Failed to create connections - please check Airflow status"
        exit 1
    fi
fi

echo ""
echo "=== Summary ==="
echo "💡 This optimization helps in scenarios where:"
echo "   • Airflow VM is restarted but connections persist"
echo "   • Pipeline runs multiple times without connection changes"
echo "   • You want to avoid unnecessary recreation of existing configs"
echo ""
echo "💰 Cost & Time Benefits:"
echo "   • Reduces pipeline execution time when connections exist"
echo "   • Minimizes unnecessary API calls to Airflow"
echo "   • Provides clear feedback about configuration state"
echo ""
echo "🔧 Usage in Jenkins:"
echo "   The Jenkins pipeline now automatically checks first and only"
echo "   creates connections/variables when they're actually missing!" 