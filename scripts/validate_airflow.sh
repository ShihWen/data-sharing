#!/bin/bash

# Airflow Validation Script
# This script validates that Airflow is running properly

set -e

echo "=== Airflow Validation Script ==="
echo "Timestamp: $(date)"
echo ""

# Get VM IP
VM_IP=$(gcloud compute instances describe airflow-vm --zone=asia-east1-b --format="get(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null || echo "")

if [ -z "$VM_IP" ]; then
    echo "❌ ERROR: Could not get VM IP. Is the VM running?"
    echo "   Run: gcloud compute instances start airflow-vm --zone=asia-east1-b"
    exit 1
fi

echo "🔍 VM IP: $VM_IP"
echo ""

# Test 1: VM Connectivity
echo "1️⃣ Testing VM connectivity..."
if ping -c 3 "$VM_IP" > /dev/null 2>&1; then
    echo "   ✅ VM is reachable"
else
    echo "   ❌ VM is not reachable"
    exit 1
fi

# Test 2: Port 8081 accessibility
echo ""
echo "2️⃣ Testing Airflow port 8081..."
if curl -s --connect-timeout 10 "http://$VM_IP:8081/health" > /dev/null; then
    echo "   ✅ Port 8081 is accessible"
else
    echo "   ❌ Port 8081 is not accessible"
    echo "   💡 Try: Check if services are running on the VM"
fi

# Test 3: Health endpoint
echo ""
echo "3️⃣ Testing Airflow health endpoint..."
HEALTH_RESPONSE=$(curl -s --connect-timeout 10 "http://$VM_IP:8081/health" 2>/dev/null || echo "")
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "   ✅ Airflow health check passed"
    echo "   📊 Health status: $(echo "$HEALTH_RESPONSE" | jq -r '.metadatabase.status // "unknown"' 2>/dev/null || echo "healthy")"
else
    echo "   ❌ Airflow health check failed"
    echo "   💡 Try: Check service logs on the VM"
fi

# Test 4: Web UI accessibility
echo ""
echo "4️⃣ Testing Airflow web UI..."
UI_RESPONSE=$(curl -s --connect-timeout 10 -w "%{http_code}" "http://$VM_IP:8081/" -o /dev/null 2>/dev/null || echo "000")
if [ "$UI_RESPONSE" = "302" ] || [ "$UI_RESPONSE" = "200" ]; then
    echo "   ✅ Web UI is accessible (HTTP $UI_RESPONSE)"
else
    echo "   ❌ Web UI is not accessible (HTTP $UI_RESPONSE)"
fi

# Test 5: Check services on VM
echo ""
echo "5️⃣ Checking services on VM..."
SERVICE_STATUS=$(gcloud compute ssh airflow-vm --zone=asia-east1-b --command="cd /opt/airflow && sudo docker-compose ps --format table" 2>/dev/null || echo "")
if echo "$SERVICE_STATUS" | grep -q "Up"; then
    echo "   ✅ Docker services are running"
    RUNNING_SERVICES=$(echo "$SERVICE_STATUS" | grep "Up" | wc -l)
    echo "   📊 Running services: $RUNNING_SERVICES"
else
    echo "   ❌ Docker services are not running properly"
    echo "   💡 Try: Restart services with docker-compose up -d"
fi

# Summary
echo ""
echo "=== Validation Summary ==="
if curl -s --connect-timeout 5 "http://$VM_IP:8081/health" > /dev/null 2>&1; then
    echo "🎉 SUCCESS: Airflow is running and accessible!"
    echo ""
    echo "🌐 Access Airflow UI: http://$VM_IP:8081"
    echo "👤 Username: admin"
    echo "🔑 Password: admin"
    echo ""
    echo "📋 Quick commands:"
    echo "   • Check services: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose ps'"
    echo "   • View logs: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose logs airflow-webserver --tail=20'"
    echo "   • Restart services: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose restart'"
else
    echo "❌ FAILED: Airflow is not working properly"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "   1. Check VM status: gcloud compute instances list --filter='name=airflow-vm'"
    echo "   2. Check startup logs: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo journalctl -u google-startup-scripts.service --no-pager | tail -50'"
    echo "   3. Check service status: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose ps'"
    echo "   4. Fix permissions: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo chown -R 50000:0 logs dags plugins config'"
    echo "   5. Restart services: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose restart'"
    echo ""
    echo "📖 For detailed troubleshooting, see: terraform/airflow/README.md"
fi 