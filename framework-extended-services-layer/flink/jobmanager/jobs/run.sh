#!/bin/bash

# Check if the VideoFrameProcessorFlink.py file exists
if [ ! -f VideoFrameProcessorFlink.py ]; then
  echo "Error: The VideoFrameProcessorFlink.py file does not exist."
  exit 1
fi

echo "Running VideoFrameProcessorFlink.py..."

# Execute the Flink program in Python
bin/flink run --python VideoFrameProcessorFlink.py

# Check the exit code
if [ $? -eq 0 ]; then
  echo "VideoFrameProcessorFlink.py executed successfully."
else
  echo "Error: VideoFrameProcessorFlink.py exited with an invalid exit code."
fi
