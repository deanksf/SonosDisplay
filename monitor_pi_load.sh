#!/bin/bash

echo "🔍 Raspberry Pi Load Monitor for Dual Sonos Displays"
echo "===================================================="

LOG_FILE="pi_load_monitor.log"
DURATION=${1:-300}  # Default 5 minutes

echo "Monitoring for $DURATION seconds..."
echo "Logging to: $LOG_FILE"
echo ""

# Function to get current stats
get_stats() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    local memory=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    local load=$(uptime | awk -F'load average:' '{ print $2 }' | awk '{ print $1 }' | sed 's/,//')
    local connections=$(netstat -an | grep :8000 | wc -l)
    
    echo "$timestamp,CPU:${cpu}%,Memory:${memory}%,Load:${load},Connections:${connections}"
}

# Create header
echo "Timestamp,CPU_Usage,Memory_Usage,Load_Average,HTTP_Connections" > $LOG_FILE

echo "Starting monitoring (Ctrl+C to stop early)..."
echo ""
echo "Real-time stats:"
echo "Time                 CPU    Memory  Load   HTTP_Conn"
echo "----                 ---    ------  ----   ---------"

start_time=$(date +%s)
while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -ge $DURATION ]; then
        break
    fi
    
    # Get and display stats
    stats=$(get_stats)
    echo "$stats" >> $LOG_FILE
    
    # Parse for display
    timestamp=$(echo $stats | cut -d',' -f1)
    cpu=$(echo $stats | cut -d',' -f2)
    memory=$(echo $stats | cut -d',' -f3)
    load=$(echo $stats | cut -d',' -f4)
    connections=$(echo $stats | cut -d',' -f5)
    
    printf "%-20s %-6s %-7s %-6s %-9s\n" \
           "$(date '+%H:%M:%S')" "$cpu" "$memory" "$load" "$connections"
    
    sleep 5
done

echo ""
echo "📊 Monitoring Complete! Analysis:"
echo "=================================="

# Analyze the data
avg_cpu=$(awk -F',' 'NR>1 {sum+=$2; count++} END {printf "%.1f", sum/count}' $LOG_FILE | sed 's/CPU://g' | sed 's/%//g')
max_cpu=$(awk -F',' 'NR>1 {if($2>max) max=$2} END {print max}' $LOG_FILE | sed 's/CPU://g' | sed 's/%//g')
avg_memory=$(awk -F',' 'NR>1 {sum+=$3; count++} END {printf "%.1f", sum/count}' $LOG_FILE | sed 's/Memory://g' | sed 's/%//g')
max_memory=$(awk -F',' 'NR>1 {if($3>max) max=$3} END {print max}' $LOG_FILE | sed 's/Memory://g' | sed 's/%//g')
avg_load=$(awk -F',' 'NR>1 {sum+=$4; count++} END {printf "%.2f", sum/count}' $LOG_FILE | sed 's/Load://g')
max_connections=$(awk -F',' 'NR>1 {if($5>max) max=$5} END {print max}' $LOG_FILE | sed 's/Connections://g')

echo "CPU Usage:"
echo "  Average: ${avg_cpu}%"
echo "  Peak:    ${max_cpu}%"
echo ""
echo "Memory Usage:"
echo "  Average: ${avg_memory}%"
echo "  Peak:    ${max_memory}%"
echo ""
echo "System Load:"
echo "  Average: ${avg_load}"
echo ""
echo "HTTP Connections:"
echo "  Peak concurrent: ${max_connections}"
echo ""

# Recommendations
echo "🎯 Recommendations:"
echo "==================="

if (( $(echo "$avg_cpu > 70" | bc -l) )); then
    echo "❌ HIGH CPU LOAD - Consider second Pi"
elif (( $(echo "$avg_cpu > 50" | bc -l) )); then
    echo "⚠️  MODERATE CPU LOAD - Monitor closely"
else
    echo "✅ CPU load acceptable for single Pi"
fi

if (( $(echo "$avg_memory > 80" | bc -l) )); then
    echo "❌ HIGH MEMORY USAGE - Consider second Pi"
elif (( $(echo "$avg_memory > 60" | bc -l) )); then
    echo "⚠️  MODERATE MEMORY USAGE - Monitor closely"
else
    echo "✅ Memory usage acceptable for single Pi"
fi

if (( $(echo "$avg_load > 2.0" | bc -l) )); then
    echo "❌ HIGH SYSTEM LOAD - Consider second Pi"
elif (( $(echo "$avg_load > 1.0" | bc -l) )); then
    echo "⚠️  MODERATE SYSTEM LOAD - Monitor closely"  
else
    echo "✅ System load acceptable for single Pi"
fi

echo ""
echo "📁 Full data saved to: $LOG_FILE"
echo "   View with: cat $LOG_FILE | column -t -s','" 