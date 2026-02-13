#!/bin/bash
# Watch Pipeline Progress

echo "==================================="
echo "KNOWLEDGEVAULT PIPELINE PROGRESS"
echo "==================================="
echo ""

# Watch the last line with percentage
tail -f pipeline.log | grep --line-buffered "Parsing emails:" | while read line; do
    clear
    echo "==================================="
    echo "KNOWLEDGEVAULT PIPELINE PROGRESS"
    echo "==================================="
    echo ""
    echo "$line"
    echo ""
    echo "Press Ctrl+C to stop watching"
    echo "==================================="
done
